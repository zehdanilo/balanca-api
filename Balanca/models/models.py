from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    text,
)
from sqlalchemy.orm import relationship

from ..database.base import Base


# Expressão SQL Server para "agora" em UTC-3
SQLSERVER_NOW_UTC_MINUS_3 = text("DATEADD(HOUR, -3, GETUTCDATE())")


class ApiAccessLog(Base):
    __tablename__ = "balanca_access_log"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # server_default evita que o SQLAlchemy envie NULL; o DB preenche.
    ts_utc = Column(DateTime, nullable=False, server_default=SQLSERVER_NOW_UTC_MINUS_3)

    client_ip = Column(String(64), nullable=False, default="")
    method = Column(String(16), nullable=False, default="")
    path = Column(String(256), nullable=False, default="")
    query_string = Column(String(1024), nullable=False, default="")
    status_code = Column(Integer, nullable=False, default=200)
    response_ms = Column(Integer, nullable=True)
    user_agent = Column(String(512), nullable=False, default="")
    auth_user = Column(String(128), nullable=False, default="")

    def to_dict(self):
        return {
            "id": self.id,
            "ts_utc": self.ts_utc.isoformat() if self.ts_utc else None,
            "client_ip": self.client_ip,
            "method": self.method,
            "path": self.path,
            "query_string": self.query_string,
            "status_code": self.status_code,
            "response_ms": self.response_ms,
            "user_agent": self.user_agent,
            "auth_user": self.auth_user,
        }


class Reading(Base):
    __tablename__ = "balanca_readings"

    id = Column(Integer, primary_key=True)

    # server_default evita INSERT com ts_utc=NULL; o DB preenche em UTC-3.
    ts_utc = Column(DateTime, nullable=False, server_default=SQLSERVER_NOW_UTC_MINUS_3)

    equip_ip = Column(String(64), nullable=False)
    equip_port = Column(Integer, nullable=False)

    swa = Column(Integer, nullable=False)
    swb = Column(Integer, nullable=False)
    swc = Column(Integer, nullable=False)

    peso = Column(Integer, nullable=False)
    tara = Column(Integer, nullable=False)

    peso_raw = Column(String(16), nullable=False)
    tara_raw = Column(String(16), nullable=False)

    checksum = Column(Integer)

    # 1 Reading -> N LatestQueryLog
    latest_queries = relationship(
        "LatestQueryLog",
        back_populates="reading",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def to_dict(self):
        return {
            "id": self.id,
            "ts_utc": self.ts_utc.isoformat() if self.ts_utc else None,
            "equip_ip": self.equip_ip,
            "equip_port": self.equip_port,
            "swa": self.swa,
            "swb": self.swb,
            "swc": self.swc,
            "peso": self.peso,
            "tara": self.tara,
            "peso_raw": self.peso_raw,
            "tara_raw": self.tara_raw,
            "checksum": self.checksum,
        }


class LatestQueryLog(Base):
    __tablename__ = "balanca_latest_query_log"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # server_default evita INSERT com ts_utc=NULL; o DB preenche em UTC-3.
    ts_utc = Column(DateTime, nullable=False, server_default=SQLSERVER_NOW_UTC_MINUS_3)

    auth_user = Column(String(128), nullable=False, default="")
    client_ip = Column(String(64), nullable=False, default="")
    user_agent = Column(String(512), nullable=False, default="")
    status_code = Column(Integer, nullable=False, default=200)
    response_ms = Column(Integer, nullable=True)

    # "db" | "memory" | "none"
    source = Column(String(16), nullable=False, default="db")

    # FK -> balanca_readings.id
    reading_id = Column(
        Integer,
        ForeignKey("balanca_readings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    reading = relationship(
        "Reading",
        back_populates="latest_queries",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "ts_utc": self.ts_utc.isoformat() if self.ts_utc else None,
            "auth_user": self.auth_user,
            "client_ip": self.client_ip,
            "user_agent": self.user_agent,
            "status_code": self.status_code,
            "response_ms": self.response_ms,
            "source": self.source,
            "reading_id": self.reading_id,
        }
