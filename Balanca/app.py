import time
import threading
import logging
import os
from pathlib import Path
from datetime import datetime, timedelta

from flask import Flask, jsonify, request, g, send_from_directory
from sqlalchemy import text, or_
from sqlalchemy.orm import selectinload

from flasgger import Swagger

from .config import settings
from .auth import require_auth

from .database.db import SessionLocal, init_db
from .models.models import (
    ApiAccessLog,
    ChemicalSpecCatalog,
    CustomerCatalog,
    DestinationCatalog,
    DriverCatalog,
    HorsePlateCatalog,
    LatestQueryLog,
    Reading,
    TankPlateCatalog,
    TransporterCatalog,
    WeighingRecord,
    WeighingTicket,
)
from .services.reader_service import ReaderService
from .catalog_seed import seed_catalog_data


ADMIN_PASSWORD = "M3dic@o"


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
    frontend_dir = Path(__file__).resolve().parent.parent / "frontend"

    init_db()
    try:
        seed_info = seed_catalog_data()
        logging.getLogger("balanca").info("Catálogos carregados: %s", seed_info)
    except Exception as e:
        logging.getLogger("balanca").exception("Falha ao carregar catálogos: %s", e)

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

    def _current_operator_payload() -> dict:
        candidates = {
            "X-User-Email": request.headers.get("X-User-Email"),
            "X-Forwarded-Email": request.headers.get("X-Forwarded-Email"),
            "X-Forwarded-User": request.headers.get("X-Forwarded-User"),
            "X-Remote-User": request.headers.get("X-Remote-User"),
            "X-Authenticated-User": request.headers.get("X-Authenticated-User"),
            "REMOTE_USER": request.environ.get("REMOTE_USER"),
            "LOGON_USER": request.environ.get("LOGON_USER"),
            "AUTH_USER": request.environ.get("AUTH_USER"),
        }

        raw_user = ""
        source = ""
        ignored_logins = {"", "ANONYMOUS", "ANONYMOUS LOGON", "IUSR"}
        for candidate_source, value in candidates.items():
            candidate = str(value or "").strip().replace("/", "\\")
            login_candidate = candidate.split("\\")[-1].strip() if candidate else ""
            if not login_candidate:
                continue
            if login_candidate.endswith("$") or login_candidate.upper() in ignored_logins:
                continue
            raw_user = candidate
            source = candidate_source
            break

        login = raw_user.split("\\")[-1] if raw_user else ""

        if "@" in login:
            username = login.split("@")[0]
            email = login
        else:
            username = login
            domain = (os.environ.get("USERDNSDOMAIN") or "").strip().lower()
            email = f"{username}@{domain}" if username and domain else username

        display = email or username or "Balança"
        return {
            "username": username or display,
            "email": display,
            "source": source,
            "authenticated": bool(raw_user),
        }

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

    def _now_local() -> datetime:
        return datetime.utcnow() - timedelta(hours=3)

    def _parse_ticket_date(value: str | None):
        if not value:
            day = _now_local().date()
        else:
            try:
                day = datetime.strptime(value.strip(), "%Y-%m-%d").date()
            except Exception:
                raise ValueError("Parâmetro date inválido. Use YYYY-MM-DD.")

        start = datetime.combine(day, datetime.min.time())
        end = start + timedelta(days=1)
        return day.isoformat(), start, end

    def _is_admin_request(data: dict | None = None) -> bool:
        admin_password = request.headers.get("X-Admin-Password") or ""
        if not admin_password and data:
            admin_password = str(data.get("admin_password") or data.get("adminPassword") or "")
        return admin_password == ADMIN_PASSWORD

    def _ticket_is_locked(ticket: WeighingTicket) -> bool:
        return (ticket.status or "").upper() == "COMPLETO"

    def _ticket_is_in_progress(ticket: WeighingTicket) -> bool:
        return (ticket.status or "").upper() == "EM_ANDAMENTO"

    def _parse_frontend_datetime(value) -> datetime:
        if not value:
            return _now_local()

        if isinstance(value, datetime):
            return value

        try:
            normalized = str(value).strip().replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
            return parsed.replace(tzinfo=None)
        except Exception:
            return _now_local()

    def _ticket_payload_value(data: dict, *names: str, default=""):
        for name in names:
            if name in data:
                value = data.get(name)
                if value is None:
                    return default
                return value
        return default

    def _normalize_text_value(value, limit: int) -> str:
        normalized = " ".join(str(value or "").strip().upper().split())
        return normalized[:limit]

    def _protected_in_progress_changes(ticket: WeighingTicket, data: dict) -> list[str]:
        protected_fields = [
            ("placa_cavalo", ("placa_cavalo", "placaCavalo"), 16, "Placa Cavalo"),
            ("placa_tanque", ("placa_tanque", "placaTanque"), 16, "Placa Tanque"),
            ("motorista", ("motorista",), 160, "Motorista"),
            ("fornecedor_cliente", ("fornecedor_cliente", "fornecedorCliente"), 180, "Fornecedor/Cliente"),
            ("transportadora", ("transportadora",), 180, "Transportadora"),
        ]
        changed = []

        for attr, names, limit, label in protected_fields:
            if not any(name in data for name in names):
                continue
            current = _normalize_text_value(getattr(ticket, attr), limit)
            incoming = _normalize_text_value(_ticket_payload_value(data, *names, default=getattr(ticket, attr)), limit)
            if incoming != current:
                changed.append(label)

        return changed

    def _generate_ticket_code(ticket_id: int) -> str:
        return f"T-{ticket_id:05d}"

    def _temporary_ticket_code() -> str:
        return "TMP-" + datetime.now().strftime("%Y%m%d%H%M%S%f")

    def _apply_ticket_payload(ticket: WeighingTicket, data: dict) -> None:
        ticket.placa_cavalo = _normalize_text_value(
            _ticket_payload_value(data, "placa_cavalo", "placaCavalo", default=ticket.placa_cavalo),
            16,
        )
        ticket.placa_tanque = _normalize_text_value(
            _ticket_payload_value(data, "placa_tanque", "placaTanque", default=ticket.placa_tanque),
            16,
        )
        ticket.motorista = _normalize_text_value(
            _ticket_payload_value(data, "motorista", default=ticket.motorista),
            160,
        )
        ticket.fornecedor_cliente = _normalize_text_value(
            _ticket_payload_value(
                data,
                "fornecedor_cliente",
                "fornecedorCliente",
                default=ticket.fornecedor_cliente,
            ),
            180,
        )
        ticket.transportadora = _normalize_text_value(
            _ticket_payload_value(data, "transportadora", default=ticket.transportadora),
            180,
        )
        ticket.produto = _normalize_text_value(
            _ticket_payload_value(data, "produto", default=ticket.produto),
            32,
        )
        ticket.especificacao_quimico = _normalize_text_value(
            _ticket_payload_value(
                data,
                "especificacao_quimico",
                "especificacaoQuimico",
                default=ticket.especificacao_quimico,
            ),
            180,
        )
        ticket.destino_procedencia = _normalize_text_value(
            _ticket_payload_value(
                data,
                "destino_procedencia",
                "destinoProcedencia",
                default=ticket.destino_procedencia,
            ),
            180,
        )
        ticket.updated_at = _now_local()

    def _ensure_catalog_value(db, model, field_name: str, value: str, limit: int) -> None:
        normalized = _normalize_text_value(value, limit)
        if not normalized:
            return

        field = getattr(model, field_name)
        exists = db.query(model).filter(field == normalized).first()
        if not exists:
            db.add(model(**{field_name: normalized}))

    def _sync_ticket_catalogs(db, ticket: WeighingTicket) -> None:
        _ensure_catalog_value(db, HorsePlateCatalog, "placa", ticket.placa_cavalo, 16)
        _ensure_catalog_value(db, TankPlateCatalog, "placa", ticket.placa_tanque, 16)
        _ensure_catalog_value(db, DriverCatalog, "nome", ticket.motorista, 160)
        _ensure_catalog_value(db, TransporterCatalog, "nome", ticket.transportadora, 180)
        _ensure_catalog_value(db, CustomerCatalog, "nome", ticket.fornecedor_cliente, 180)
        _ensure_catalog_value(db, ChemicalSpecCatalog, "nome", ticket.especificacao_quimico, 180)
        _ensure_catalog_value(db, DestinationCatalog, "nome", ticket.destino_procedencia, 180)

    def _catalog_rows(db, model, catalog_field, key: str, q: str, limit: int):
        query = db.query(model)
        if q:
            query = query.filter(catalog_field.ilike(f"%{_normalize_text_value(q, 180)}%"))

        return [
            {"id": row.id, key: _normalize_text_value(getattr(row, catalog_field.key), 180)}
            for row in query.order_by(catalog_field.asc()).limit(limit).all()
        ]

    def _catalog_rows_from_sources(db, model, catalog_field, ticket_field, key: str, q: str, limit: int):
        seen = set()
        rows = []

        def add_value(value, row_id=None):
            normalized = _normalize_text_value(value, 180)
            if not normalized or normalized in seen:
                return
            seen.add(normalized)
            rows.append({"id": row_id, key: normalized})

        ticket_query = db.query(ticket_field).filter(ticket_field != "")
        if q:
            ticket_query = ticket_query.filter(ticket_field.ilike(f"%{q}%"))
        for (value,) in ticket_query.order_by(WeighingTicket.updated_at.desc()).limit(limit * 4).all():
            add_value(value)
            if len(rows) >= limit:
                return rows

        catalog_query = db.query(model)
        if q:
            catalog_query = catalog_query.filter(catalog_field.ilike(f"%{q}%"))
        for row in catalog_query.order_by(model.created_at.desc(), catalog_field.asc()).limit(limit * 4).all():
            add_value(getattr(row, catalog_field.key), row.id)
            if len(rows) >= limit:
                return rows

        return rows

    def _refresh_ticket_weights(ticket: WeighingTicket) -> None:
        rows = sorted(ticket.weighings or [], key=lambda row: row.sequencia)
        if not rows:
            ticket.peso_inicial = None
            ticket.peso_final = None
            ticket.peso_liquido = None
            return

        first = rows[0].peso
        last = rows[-1].peso
        ticket.peso_inicial = first
        ticket.peso_final = last if len(rows) >= 2 else None
        if len(rows) >= 2 and len(rows) % 2 == 0:
            total_liquido = 0
            for idx in range(0, len(rows), 2):
                total_liquido += abs(rows[idx].peso - rows[idx + 1].peso)
            ticket.peso_liquido = total_liquido
        else:
            ticket.peso_liquido = None

    def _next_weighing_type(sequence: int) -> str:
        if sequence % 2 == 0:
            return "SAIDA"
        return "ENTRADA"

    def _latest_scale_payload(db) -> dict | None:
        mem_payload = reader.get_latest_reading_dict()
        if mem_payload:
            try:
                persist_info = reader.persist_latest_if_needed()
                return persist_info.get("reading") or mem_payload
            except Exception as e:
                log.exception("Falha ao persistir latest para ticket: %s", e)
                return mem_payload

        row = db.query(Reading).order_by(Reading.ts_utc.desc(), Reading.id.desc()).first()
        return row.to_dict() if row else None

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
    @app.get("/")
    def frontend_index():
        return send_from_directory(frontend_dir, "index.html")

    @app.get("/frontend/<path:filename>")
    def frontend_assets(filename: str):
        return send_from_directory(frontend_dir, filename)

    @app.get("/whoami")
    def whoami():
        return ok(_current_operator_payload())

    @app.get("/catalog/tank-plates")
    def catalog_tank_plates():
        q = (request.args.get("q") or "").strip()
        limit = request.args.get("limit", "300")
        try:
            n = int(limit)
            if n < 1 or n > 1000:
                return fail("Parâmetro limit deve estar entre 1 e 1000.", 400)
        except ValueError:
            return fail("Parâmetro limit inválido.", 400)

        db = SessionLocal()
        try:
            rows = _catalog_rows_from_sources(
                db, TankPlateCatalog, TankPlateCatalog.placa, WeighingTicket.placa_tanque, "placa", q, n
            )
            return ok(rows, limit=n)
        finally:
            db.close()

    @app.get("/catalog/horse-plates")
    def catalog_horse_plates():
        q = (request.args.get("q") or "").strip()
        limit = request.args.get("limit", "300")
        try:
            n = int(limit)
            if n < 1 or n > 1000:
                return fail("Parâmetro limit deve estar entre 1 e 1000.", 400)
        except ValueError:
            return fail("Parâmetro limit inválido.", 400)

        db = SessionLocal()
        try:
            rows = _catalog_rows_from_sources(
                db, HorsePlateCatalog, HorsePlateCatalog.placa, WeighingTicket.placa_cavalo, "placa", q, n
            )
            return ok(rows, limit=n)
        finally:
            db.close()

    @app.get("/catalog/drivers")
    def catalog_drivers():
        q = (request.args.get("q") or "").strip()
        limit = request.args.get("limit", "300")
        try:
            n = int(limit)
            if n < 1 or n > 1000:
                return fail("Parâmetro limit deve estar entre 1 e 1000.", 400)
        except ValueError:
            return fail("Parâmetro limit inválido.", 400)

        db = SessionLocal()
        try:
            rows = _catalog_rows_from_sources(
                db, DriverCatalog, DriverCatalog.nome, WeighingTicket.motorista, "nome", q, n
            )
            return ok(rows, limit=n)
        finally:
            db.close()

    @app.get("/catalog/transporters")
    def catalog_transporters():
        q = (request.args.get("q") or "").strip()
        limit = request.args.get("limit", "300")
        try:
            n = int(limit)
            if n < 1 or n > 1000:
                return fail("Parâmetro limit deve estar entre 1 e 1000.", 400)
        except ValueError:
            return fail("Parâmetro limit inválido.", 400)

        db = SessionLocal()
        try:
            rows = _catalog_rows_from_sources(
                db, TransporterCatalog, TransporterCatalog.nome, WeighingTicket.transportadora, "nome", q, n
            )
            return ok(rows, limit=n)
        finally:
            db.close()

    @app.get("/catalog/customers")
    def catalog_customers():
        q = (request.args.get("q") or "").strip()
        limit = request.args.get("limit", "300")
        try:
            n = int(limit)
            if n < 1 or n > 1000:
                return fail("Parâmetro limit deve estar entre 1 e 1000.", 400)
        except ValueError:
            return fail("Parâmetro limit inválido.", 400)

        db = SessionLocal()
        try:
            return ok(_catalog_rows(db, CustomerCatalog, CustomerCatalog.nome, "nome", q, n), limit=n)
        finally:
            db.close()

    @app.get("/catalog/chemical-specs")
    def catalog_chemical_specs():
        q = (request.args.get("q") or "").strip()
        limit = request.args.get("limit", "300")
        try:
            n = int(limit)
            if n < 1 or n > 1000:
                return fail("Parâmetro limit deve estar entre 1 e 1000.", 400)
        except ValueError:
            return fail("Parâmetro limit inválido.", 400)

        db = SessionLocal()
        try:
            return ok(_catalog_rows(db, ChemicalSpecCatalog, ChemicalSpecCatalog.nome, "nome", q, n), limit=n)
        finally:
            db.close()

    @app.get("/catalog/destinations")
    def catalog_destinations():
        q = (request.args.get("q") or "").strip()
        limit = request.args.get("limit", "300")
        try:
            n = int(limit)
            if n < 1 or n > 1000:
                return fail("Parâmetro limit deve estar entre 1 e 1000.", 400)
        except ValueError:
            return fail("Parâmetro limit inválido.", 400)

        db = SessionLocal()
        try:
            return ok(_catalog_rows(db, DestinationCatalog, DestinationCatalog.nome, "nome", q, n), limit=n)
        finally:
            db.close()

    @app.get("/tickets")
    def tickets():
        q = (request.args.get("q") or "").strip()
        status = (request.args.get("status") or "").strip().upper()
        date_value = (request.args.get("date") or "").strip()
        limit = request.args.get("limit", "100")

        try:
            n = int(limit)
            if n < 1 or n > 500:
                return fail("Parâmetro limit deve estar entre 1 e 500.", 400)
        except ValueError:
            return fail("Parâmetro limit inválido.", 400)

        try:
            selected_date, day_start, day_end = _parse_ticket_date(date_value)
        except ValueError as e:
            return fail(str(e), 400)

        db = SessionLocal()
        try:
            query = db.query(WeighingTicket).options(selectinload(WeighingTicket.weighings))
            query = query.filter(
                WeighingTicket.created_at >= day_start,
                WeighingTicket.created_at < day_end,
            )
            if status:
                query = query.filter(WeighingTicket.status == status)
            if q:
                like = f"%{q}%"
                query = query.filter(
                    or_(
                        WeighingTicket.ticket_code.ilike(like),
                        WeighingTicket.placa_cavalo.ilike(like),
                        WeighingTicket.placa_tanque.ilike(like),
                        WeighingTicket.motorista.ilike(like),
                        WeighingTicket.fornecedor_cliente.ilike(like),
                        WeighingTicket.transportadora.ilike(like),
                        WeighingTicket.produto.ilike(like),
                        WeighingTicket.destino_procedencia.ilike(like),
                    )
                )

            rows = query.order_by(WeighingTicket.updated_at.desc(), WeighingTicket.id.desc()).limit(n).all()
            return ok([row.to_dict(include_weighings=True) for row in rows], limit=n, date=selected_date, timezone="GMT-3")
        finally:
            db.close()

    @app.post("/tickets")
    def create_ticket():
        data = request.get_json(silent=True) or {}
        db = SessionLocal()
        try:
            ticket = WeighingTicket(ticket_code=_temporary_ticket_code(), status="ABERTO")
            _apply_ticket_payload(ticket, data)
            _sync_ticket_catalogs(db, ticket)
            db.add(ticket)
            db.flush()
            ticket.ticket_code = _generate_ticket_code(ticket.id)
            db.commit()
            db.refresh(ticket)
            return ok(ticket.to_dict())
        finally:
            db.close()

    @app.get("/tickets/<int:ticket_id>")
    def get_ticket(ticket_id: int):
        db = SessionLocal()
        try:
            ticket = db.query(WeighingTicket).filter(WeighingTicket.id == ticket_id).first()
            if not ticket:
                return fail("Ticket não encontrado.", 404)
            return ok(ticket.to_dict())
        finally:
            db.close()

    @app.patch("/tickets/<int:ticket_id>")
    def update_ticket(ticket_id: int):
        data = request.get_json(silent=True) or {}
        db = SessionLocal()
        try:
            ticket = db.query(WeighingTicket).filter(WeighingTicket.id == ticket_id).first()
            if not ticket:
                return fail("Ticket não encontrado.", 404)
            if _ticket_is_locked(ticket) and not _is_admin_request(data):
                return fail("Ticket encerrado. Confirmação admin necessária para alterar.", 403)
            if _ticket_is_in_progress(ticket) and not _is_admin_request(data):
                blocked = _protected_in_progress_changes(ticket, data)
                if blocked:
                    return fail(
                        "Ticket em andamento. Senha admin necessária para alterar: " + ", ".join(blocked) + ".",
                        403,
                    )

            _apply_ticket_payload(ticket, data)
            _sync_ticket_catalogs(db, ticket)
            db.commit()
            db.refresh(ticket)
            return ok(ticket.to_dict())
        finally:
            db.close()

    @app.delete("/tickets/<int:ticket_id>")
    def delete_ticket(ticket_id: int):
        data = request.get_json(silent=True) or {}
        db = SessionLocal()
        try:
            ticket = db.query(WeighingTicket).filter(WeighingTicket.id == ticket_id).first()
            if not ticket:
                return fail("Ticket não encontrado.", 404)
            if _ticket_is_locked(ticket) and not _is_admin_request(data):
                return fail("Ticket encerrado. Confirmação admin necessária para excluir.", 403)

            db.delete(ticket)
            db.commit()
            return ok({"deleted": True, "id": ticket_id})
        finally:
            db.close()

    @app.post("/tickets/<int:ticket_id>/close")
    def close_ticket(ticket_id: int):
        db = SessionLocal()
        try:
            ticket = db.query(WeighingTicket).filter(WeighingTicket.id == ticket_id).first()
            if not ticket:
                return fail("Ticket não encontrado.", 404)
            if _ticket_is_locked(ticket):
                return ok(ticket.to_dict())

            weighing_count = len(ticket.weighings or [])
            if weighing_count == 0 or weighing_count % 2 != 0:
                return fail("O ticket só pode ser encerrado após uma quantidade par de pesagens.", 400)

            _refresh_ticket_weights(ticket)
            ticket.status = "COMPLETO"
            ticket.completed_at = _now_local()
            ticket.updated_at = _now_local()
            db.commit()
            db.refresh(ticket)
            return ok(ticket.to_dict())
        finally:
            db.close()

    @app.post("/tickets/<int:ticket_id>/weighings")
    def add_ticket_weighing(ticket_id: int):
        data = request.get_json(silent=True) or {}
        db = SessionLocal()
        try:
            ticket = db.query(WeighingTicket).filter(WeighingTicket.id == ticket_id).first()
            if not ticket:
                return fail("Ticket não encontrado.", 404)
            if _ticket_is_locked(ticket) and not _is_admin_request(data):
                return fail("Ticket encerrado. Confirmação admin necessária para registrar nova pesagem.", 403)

            scale_payload = None
            if data.get("peso") is None:
                scale_payload = _latest_scale_payload(db)
                if not scale_payload:
                    return fail("A API ainda não possui leitura válida da balança.", 400)

            source = scale_payload or data
            try:
                raw_peso = source.get("peso")
                if raw_peso is None:
                    raw_peso = source.get("weight")
                peso = int(float(raw_peso))
            except Exception:
                return fail("Peso inválido para a pesagem.", 400)

            sequence = len(ticket.weighings or []) + 1
            operator_payload = _current_operator_payload()
            record = WeighingRecord(
                ticket_id=ticket.id,
                reading_id=source.get("id") or data.get("reading_id") or data.get("readingId"),
                sequencia=sequence,
                tipo=_next_weighing_type(sequence),
                data_hora=_parse_frontend_datetime(
                    source.get("ts_utc") or data.get("data_hora") or data.get("dataHora")
                ),
                balanca=str(data.get("balanca") or "Balança 002")[:80],
                peso=peso,
                operador=str(data.get("operador") or data.get("operator") or operator_payload.get("email") or "Balança")[:120],
            )

            db.add(record)
            db.flush()
            ticket.weighings.append(record)
            ticket.status = "COMPLETO" if bool(data.get("finalizar")) else "EM_ANDAMENTO"
            ticket.completed_at = _now_local() if ticket.status == "COMPLETO" else None
            ticket.updated_at = _now_local()
            _refresh_ticket_weights(ticket)

            db.commit()
            db.refresh(ticket)
            return ok(ticket.to_dict())
        finally:
            db.close()

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
