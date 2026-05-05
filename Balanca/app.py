import time
import threading
import logging
import os

from flask import Flask, jsonify, request, g
from sqlalchemy import text

from flasgger import Swagger

from .config import settings
from .auth import require_auth

from .database.db import SessionLocal, init_db
from .models.models import ApiAccessLog, Reading, LatestQueryLog
from .services.reader_service import ReaderService


SWAGGER_CONFIG = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec_1",
            "route": "/apispec_1.json",
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/swagger/",
}

SWAGGER_TEMPLATE = {
    "swagger": "2.0",
    "info": {
        "title": "BALANCA API",
        "version": "1.0.0",
        "description": "API de leitura P03 via TCP com persistência em SQL Server (sob demanda e/ou agendada)",
    },
    "securityDefinitions": {"basicAuth": {"type": "basic"}},
    "paths": {},
}


def create_app() -> Flask:
    app = Flask(__name__)
    Swagger(app, config=SWAGGER_CONFIG, template=SWAGGER_TEMPLATE)

    init_db()

    logging.basicConfig(level=logging.INFO)
    log = logging.getLogger("balanca")

    reader = ReaderService(settings=settings)

    # -----------------------------
    # AUTO-START DO READER (BOOT)
    # -----------------------------
    _autostart_lock = threading.Lock()
    _autostart_done = {"value": False}

    def _autostart_reader():
        try:
            delay = float(getattr(settings, "AUTO_START_DELAY_S", 1.0) or 1.0)
            time.sleep(max(0.0, delay))

            with _autostart_lock:
                if _autostart_done["value"]:
                    return
                _autostart_done["value"] = True

            if not getattr(settings, "AUTO_START_READER", True):
                log.info("AUTO_START_READER=false; Reader não será iniciado automaticamente.")
                return

            started = reader.start()
            log.info("Auto-start do reader executado. started=%s status=%s", started, reader.status())
        except Exception as e:
            log.exception("Falha no auto-start do reader: %s", e)

    threading.Thread(target=_autostart_reader, name="reader-autostart", daemon=True).start()

    # -----------------------------
    # AUTO-PERSIST (SCHEDULER INTERNO)
    # -----------------------------
    _autopersist_lock = threading.Lock()
    _autopersist_done = {"value": False}
    _autopersist_stop = threading.Event()

    def _should_start_scheduler() -> bool:
        """
        Evita duplicação:
        - Em Flask debug com reloader, só roda no processo 'principal' do reloader.
        - Em produção, roda normalmente.
        """
        if not getattr(settings, "AUTO_PERSIST_LATEST", True):
            return False

        # Se debug e reloader ativo, o processo pai não deve rodar threads de background.
        if getattr(settings, "FLASK_DEBUG", False):
            # WERKZEUG_RUN_MAIN='true' no processo que realmente serve requests
            return os.environ.get("WERKZEUG_RUN_MAIN") == "true"

        return True

    def _autopersist_loop():
        try:
            interval = float(getattr(settings, "AUTO_PERSIST_INTERVAL_S", 60.0) or 60.0)
            interval = max(5.0, interval)  # defesa

            with _autopersist_lock:
                if _autopersist_done["value"]:
                    return
                _autopersist_done["value"] = True

            log.info("Auto-persist habilitado. Intervalo=%.1fs", interval)

            # pequeno delay para permitir o reader iniciar e popular _latest
            time.sleep(2.0)

            while not _autopersist_stop.is_set():
                try:
                    # persiste a última leitura disponível (se houver)
                    info = reader.persist_latest_if_needed()

                    # log sucinto (não vaza segredos)
                    reason = info.get("reason")
                    persisted = bool(info.get("persisted"))
                    rid = None
                    reading = info.get("reading") or {}
                    if isinstance(reading, dict):
                        rid = reading.get("id")

                    log.info("Auto-persist tick: reason=%s persisted=%s reading_id=%s", reason, persisted, rid)

                except Exception as e:
                    log.exception("Falha no auto-persist tick: %s", e)

                # sleep interruptível
                end = time.time() + interval
                while time.time() < end:
                    if _autopersist_stop.is_set():
                        break
                    time.sleep(0.2)

        except Exception as e:
            log.exception("Falha no loop do auto-persist: %s", e)

    if _should_start_scheduler():
        threading.Thread(target=_autopersist_loop, name="latest-autopersist", daemon=True).start()
    else:
        log.info("Auto-persist não iniciado (AUTO_PERSIST_LATEST=false ou reloader/debug processo pai).")

    # -----------------------------
    # HELPERS
    # -----------------------------
    def _client_ip() -> str:
        xff = request.headers.get("X-Forwarded-For", "").strip()
        return ((xff.split(",")[0].strip() if xff else request.remote_addr) or "")[:64]

    def _user_agent() -> str:
        return (request.headers.get("User-Agent") or "")[:512]

    def ok(data=None, **meta):
        payload = {"ok": True, "data": data}
        if meta:
            payload["meta"] = meta
        return jsonify(payload)

    def fail(message: str, status: int = 400, **meta):
        payload = {"ok": False, "error": {"message": message}}
        if meta:
            payload["meta"] = meta
        return jsonify(payload), status

    # -----------------------------
    # TIMING + LOG GENÉRICO
    # -----------------------------
    @app.before_request
    def _start_timer():
        g._t0 = time.perf_counter()

    @app.after_request
    def _log_access(response):
        try:
            if not settings.LOG_API_ACCESS:
                return response

            t0 = getattr(g, "_t0", None)
            elapsed_ms = None
            if t0 is not None:
                elapsed_ms = int((time.perf_counter() - t0) * 1000)

            auth_user = getattr(g, "auth_user", "") or ""

            db = SessionLocal()
            try:
                db.add(
                    ApiAccessLog(
                        ts_utc=None,  # default no banco
                        client_ip=_client_ip(),
                        method=request.method,
                        path=request.path[:256],
                        query_string=(
                            request.query_string.decode("utf-8", errors="ignore")
                            if request.query_string
                            else ""
                        )[:1024],
                        status_code=int(response.status_code),
                        response_ms=elapsed_ms,
                        user_agent=_user_agent(),
                        auth_user=auth_user,
                    )
                )
                db.commit()
            finally:
                db.close()
        except Exception:
            pass

        return response

    # -----------------------------
    # ENDPOINTS
    # -----------------------------
    @app.get("/health")
    def health():
        db_ok = False
        db_err = None
        try:
            db = SessionLocal()
            try:
                db.execute(text("SELECT 1"))
                db_ok = True
            finally:
                db.close()
        except Exception as e:
            db_err = str(e)

        data = {
            "api": {"status": "ok"},
            "reader": reader.status(),
            "db": {"ok": db_ok, "error": db_err},
            "auto_persist": {
                "enabled": bool(getattr(settings, "AUTO_PERSIST_LATEST", True)),
                "interval_s": float(getattr(settings, "AUTO_PERSIST_INTERVAL_S", 300.0) or 300.0),
            },
        }
        return ok(data)

    @app.post("/start")
    @require_auth
    def start():
        started = reader.start()
        return ok({"started": started, "status": reader.status()})

    @app.post("/stop")
    @require_auth
    def stop():
        stopped = reader.stop()
        return ok({"stopped": stopped, "status": reader.status()})

    @app.get("/latest")
    @require_auth
    def latest():
        t0 = getattr(g, "_t0", None)
        auth_user = getattr(g, "auth_user", "") or ""
        status_code = 200

        source = "none"
        data = None
        note = None
        reading_id = None

        mem_payload = reader.get_latest_reading_dict()
        if mem_payload:
            source = "memory"
            try:
                persist_info = reader.persist_latest_if_needed()

                if persist_info.get("reason") == "ok":
                    data = persist_info.get("reading") or mem_payload
                    note = "Leitura persistida no banco sob demanda."
                elif persist_info.get("reason") == "error":
                    data = mem_payload
                    note = "Falha ao persistir no banco; retornando leitura de memória."
                else:
                    data = mem_payload
            except Exception as e:
                log.exception("Falha ao persistir latest sob demanda: %s", e)
                data = mem_payload
                note = "Falha ao persistir no banco; retornando leitura de memória."

        if not data:
            try:
                db = SessionLocal()
                try:
                    row = db.query(Reading).order_by(Reading.ts_utc.desc(), Reading.id.desc()).first()
                    if row:
                        data = row.to_dict()
                        source = "db"
                finally:
                    db.close()
            except Exception as e:
                log.exception("Falha ao consultar Reading no banco (fallback): %s", e)

        try:
            if isinstance(data, dict):
                rid = data.get("id", None)
                if rid is not None:
                    reading_id = int(rid)
        except Exception:
            reading_id = None

        try:
            elapsed_ms = None
            if t0 is not None:
                elapsed_ms = int((time.perf_counter() - t0) * 1000)

            db2 = SessionLocal()
            try:
                db2.add(
                    LatestQueryLog(
                        ts_utc=None,  # default no banco
                        auth_user=auth_user,
                        client_ip=_client_ip(),
                        user_agent=_user_agent(),
                        response_ms=elapsed_ms,
                        status_code=status_code,
                        source=source,
                        reading_id=reading_id,
                    )
                )
                db2.commit()
            finally:
                db2.close()
        except Exception:
            pass

        if not data:
            return ok(None, note="Sem leitura válida ainda.", source=source)

        if note:
            return ok(data, source=source, note=note)

        return ok(data, source=source)

    @app.get("/readings")
    @require_auth
    def readings():
        limit = request.args.get("limit", "100")
        try:
            n = int(limit)
            if n < 1 or n > 5000:
                return fail("Parâmetro limit deve estar entre 1 e 5000.", 400)
        except ValueError:
            return fail("Parâmetro limit inválido.", 400)

        rows = reader.fetch_last_readings(limit=n)
        return ok(rows, limit=n)

    @app.get("/access-log")
    @require_auth
    def access_log():
        limit = request.args.get("limit", "200")
        try:
            n = int(limit)
            if n < 1 or n > 5000:
                return fail("Parâmetro limit deve estar entre 1 e 5000.", 400)
        except ValueError:
            return fail("Parâmetro limit inválido.", 400)

        rows = reader.fetch_access_log(limit=n)
        return ok(rows, limit=n)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host=settings.APP_HOST, port=settings.APP_PORT, debug=settings.FLASK_DEBUG)
