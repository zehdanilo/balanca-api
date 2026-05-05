import socket
import threading
import time
import logging
import hashlib
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select, desc
from Balanca.config import Settings
from Balanca.database.db import SessionLocal
from Balanca.models.models import Reading, ApiAccessLog
from Balanca.protocols.p03_protocol import iter_p03_frames, parse_p03_frame


def _parse_backoff_list(s: str) -> List[float]:
    out: List[float] = []
    for part in (s or "").split(","):
        part = part.strip()
        if not part:
            continue
        out.append(float(part))
    return out or [1, 2, 5, 10, 30]


class ReaderService:
    """
    Reader TCP do protocolo P03:
      - mantém a última leitura em memória (self._latest)
      - NÃO persiste automaticamente no banco
      - persistência é sob demanda (endpoint /latest)
    """

    def __init__(self, settings: Settings):
        self.settings = settings

        self._log = logging.getLogger("p03.reader")
        logging.basicConfig(
            level=getattr(logging, (self.settings.LOG_LEVEL or "INFO").upper(), logging.INFO),
            format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        )

        self._stop_evt = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self._lock = threading.Lock()
        self._latest: Optional[Dict[str, Any]] = None

        # dedupe de persistência sob demanda
        self._last_persisted_fingerprint: Optional[str] = None

        self._backoff = _parse_backoff_list(getattr(self.settings, "RECONNECT_BACKOFF_S", "") or "")

    def status(self) -> Dict[str, Any]:
        running = self._thread is not None and self._thread.is_alive()
        return {
            "running": running,
            "tcp_ip": self.settings.TCP_IP,
            "tcp_port": self.settings.TCP_PORT,
            "cs_required": bool(self.settings.CS_REQUIRED),
            "cs_optional": bool(self.settings.CS_OPTIONAL),
        }

    def start(self) -> bool:
        if self._thread is not None and self._thread.is_alive():
            return False
        self._stop_evt.clear()
        self._thread = threading.Thread(target=self._run, name="p03-reader", daemon=True)
        self._thread.start()
        return True

    def stop(self) -> bool:
        if self._thread is None:
            return False
        self._stop_evt.set()
        return True

    def get_latest(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            return dict(self._latest) if self._latest else None

    def get_latest_reading_dict(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            latest = dict(self._latest) if self._latest else None
        if not latest:
            return None
        return self._rec_to_reading_payload(latest)

    def fetch_last_readings(self, limit: int = 100) -> List[Dict[str, Any]]:
        db = SessionLocal()
        try:
            q = select(Reading).order_by(desc(Reading.id)).limit(limit)
            rows = db.execute(q).scalars().all()
            return [r.to_dict() for r in rows]
        finally:
            db.close()

    def fetch_access_log(self, limit: int = 200) -> List[Dict[str, Any]]:
        db = SessionLocal()
        try:
            q = select(ApiAccessLog).order_by(desc(ApiAccessLog.id)).limit(limit)
            rows = db.execute(q).scalars().all()
            return [a.to_dict() for a in rows]
        finally:
            db.close()

    def persist_latest_if_needed(self) -> Dict[str, Any]:
        with self._lock:
            latest = dict(self._latest) if self._latest else None

        if not latest:
            return {"attempted": False, "persisted": False, "reason": "no_latest", "fingerprint": None, "reading": None}

        fp = self._fingerprint(latest)
        
        inserted = self._persist_reading(latest)
        if inserted:
            self._last_persisted_fingerprint = fp
            return {"attempted": True, "persisted": True, "reason": "ok", "fingerprint": fp, "reading": inserted}

        return {"attempted": True, "persisted": False, "reason": "error", "fingerprint": fp, "reading": None}

    # -----------------------
    # Internals
    # -----------------------
    def _rec_to_reading_payload(self, rec: Dict[str, Any]) -> Dict[str, Any]:
        equip_ip = rec.get("equip_ip") or getattr(self.settings, "TCP_IP", "") or ""
        equip_port = rec.get("equip_port", None)
        if equip_port is None:
            equip_port = getattr(self.settings, "TCP_PORT", 0)

        return {
            "id": rec.get("id"),
            "ts_utc": rec.get("ts_utc"),
            "equip_ip": str(equip_ip)[:64],
            "equip_port": int(equip_port),
            "swa": int(rec.get("swa", 0)),
            "swb": int(rec.get("swb", 0)),
            "swc": int(rec.get("swc", 0)),
            "peso": int(rec.get("peso", 0)),
            "tara": int(rec.get("tara", 0)),
            "peso_raw": str(rec.get("peso_raw") or "")[:16],
            "tara_raw": str(rec.get("tara_raw") or "")[:16],
            "checksum": (int(rec["checksum"]) if rec.get("checksum") is not None else None),
        }

    def _fetch_db_latest_as_dict_best_effort(self) -> Optional[Dict[str, Any]]:
        db = SessionLocal()
        try:
            row = db.query(Reading).order_by(Reading.ts_utc.desc(), Reading.id.desc()).first()
            return row.to_dict() if row else None
        except Exception:
            return None
        finally:
            db.close()

    def _fingerprint(self, rec: Dict[str, Any]) -> str:
        equip_ip = (rec.get("equip_ip") or getattr(self.settings, "TCP_IP", "") or "").strip()
        equip_port = rec.get("equip_port", None)
        if equip_port is None:
            equip_port = getattr(self.settings, "TCP_PORT", 0)

        parts: Tuple[str, ...] = (
            str(equip_ip),
            str(int(equip_port)),
            str(int(rec.get("swa", 0))),
            str(int(rec.get("swb", 0))),
            str(int(rec.get("swc", 0))),
            str(int(rec.get("peso", 0))),
            str(int(rec.get("tara", 0))),
            str(rec.get("peso_raw") or ""),
            str(rec.get("tara_raw") or ""),
            "" if rec.get("checksum") is None else str(int(rec.get("checksum"))),
        )
        blob = "|".join(parts).encode("utf-8", errors="strict")
        return hashlib.sha256(blob).hexdigest()

    def _run(self):
        attempt = 0
        while not self._stop_evt.is_set():
            try:
                self._connect_loop()
                attempt = 0
            except Exception as e:
                attempt += 1
                wait_s = self._backoff[min(attempt - 1, len(self._backoff) - 1)]
                self._log.error("Falha no loop TCP (%s). Reconnect em %.1fs.", str(e), wait_s)
                self._sleep_interruptible(wait_s)

    def _sleep_interruptible(self, seconds: float):
        end = time.time() + seconds
        while time.time() < end:
            if self._stop_evt.is_set():
                return
            time.sleep(0.1)

    def _connect_loop(self):
        ip = self.settings.TCP_IP
        port = self.settings.TCP_PORT
        timeout = self.settings.TCP_TIMEOUT_S

        self._log.info("Conectando em %s:%s (timeout=%.1fs)...", ip, port, timeout)

        with socket.create_connection((ip, port), timeout=timeout) as s:
            s.settimeout(timeout)
            self._log.info("Conectado em %s:%s.", ip, port)

            for raw in iter_p03_frames(s):
                if self._stop_evt.is_set():
                    self._log.info("Stop solicitado. Encerrando reader.")
                    return

                if self.settings.CS_REQUIRED and len(raw) != 18:
                    self._log.warning("Descartando frame sem CS (len=%d) - CS_REQUIRED=true.", len(raw))
                    continue

                try:
                    fr = parse_p03_frame(raw)
                except Exception as e:
                    self._log.warning(
                        "Frame inválido (len=%d, hex=%s): %s",
                        len(raw),
                        raw.hex().upper(),
                        str(e),
                    )
                    continue

                rec: Dict[str, Any] = {
                    "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "equip_ip": ip,
                    "equip_port": port,
                    "swa": fr.swa,
                    "swb": fr.swb,
                    "swc": fr.swc,
                    "peso_raw": fr.peso_raw,
                    "tara_raw": fr.tara_raw,
                    "peso": fr.peso,
                    "tara": fr.tara,
                    "checksum": fr.checksum,
                    "frame_len": len(raw),
                    "raw_hex": raw.hex().upper(),
                }

                with self._lock:
                    self._latest = dict(rec)

    def _persist_reading(self, rec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Importante:
          - NÃO setar ts_utc aqui.
          - Com server_default no model + DEFAULT no SQL Server, o DB preenche ts_utc (UTC-3).
        """
        db = SessionLocal()
        try:
            equip_ip = rec.get("equip_ip") or getattr(self.settings, "TCP_IP", None) or ""
            equip_port = rec.get("equip_port", None)
            if equip_port is None:
                equip_port = getattr(self.settings, "TCP_PORT", None)

            if not equip_ip or equip_port is None:
                self._log.error("Leitura sem equip_ip/equip_port. Não persistido. rec=%s", rec)
                return None

            obj = Reading(
                equip_ip=str(equip_ip)[:64],
                equip_port=int(equip_port),
                swa=int(rec["swa"]),
                swb=int(rec["swb"]),
                swc=int(rec["swc"]),
                peso=int(rec["peso"]),
                tara=int(rec["tara"]),
                peso_raw=str(rec["peso_raw"])[:16],
                tara_raw=str(rec["tara_raw"])[:16],
                checksum=(int(rec["checksum"]) if rec.get("checksum") is not None else None),
            )
            db.add(obj)

            db.commit()
            try:
                db.refresh(obj)
            except Exception:
                pass

            return obj.to_dict()
        except Exception as e:
            db.rollback()
            self._log.error("Falha ao persistir leitura no SQL Server: %s", str(e))
            return None
        finally:
            db.close()
