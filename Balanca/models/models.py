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


def _operator_label(value) -> str:
    normalized = " ".join(str(value or "").strip().split())
    ignored = {"", "BALANCA", "BALANÇA", "USUARIO NAO IDENTIFICADO", "USUÁRIO NÃO IDENTIFICADO"}
    return "Balança" if normalized.upper() in ignored else normalized


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


class WeighingTicket(Base):
    __tablename__ = "balanca_weighing_tickets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_code = Column(String(32), nullable=False, unique=True, index=True)
    status = Column(String(24), nullable=False, default="ABERTO", index=True)

    placa_cavalo = Column(String(16), nullable=False, default="")
    placa_tanque = Column(String(16), nullable=False, default="")
    motorista = Column(String(160), nullable=False, default="")
    fornecedor_cliente = Column(String(180), nullable=False, default="")
    transportadora = Column(String(180), nullable=False, default="")
    produto = Column(String(32), nullable=False, default="")
    especificacao_quimico = Column(String(180), nullable=False, default="")
    destino_procedencia = Column(String(180), nullable=False, default="")
    tara = Column(Integer, nullable=True)
    num_agendamento = Column(String(80), nullable=True, default="")
    lacre = Column(String(500), nullable=True, default="")
    observacao = Column(String(500), nullable=True, default="")

    peso_inicial = Column(Integer, nullable=True)
    peso_final = Column(Integer, nullable=True)
    peso_liquido = Column(Integer, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=SQLSERVER_NOW_UTC_MINUS_3)
    updated_at = Column(DateTime, nullable=False, server_default=SQLSERVER_NOW_UTC_MINUS_3)
    completed_at = Column(DateTime, nullable=True)

    weighings = relationship(
        "WeighingRecord",
        back_populates="ticket",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="WeighingRecord.sequencia",
    )

    def to_dict(self, include_weighings: bool = True):
        data = {
            "id": self.id,
            "ticket_code": self.ticket_code,
            "status": self.status,
            "placa_cavalo": self.placa_cavalo,
            "placa_tanque": self.placa_tanque,
            "motorista": self.motorista,
            "fornecedor_cliente": self.fornecedor_cliente,
            "transportadora": self.transportadora,
            "produto": self.produto,
            "especificacao_quimico": self.especificacao_quimico,
            "destino_procedencia": self.destino_procedencia,
            "tara": self.tara,
            "num_agendamento": self.num_agendamento or "",
            "lacre": self.lacre or "",
            "observacao": self.observacao or "",
            "peso_inicial": self.peso_inicial,
            "peso_final": self.peso_final,
            "peso_liquido": self.peso_liquido,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "pesagens_count": len(self.weighings or []),
        }
        if include_weighings:
            data["pesagens"] = [row.to_dict() for row in self.weighings]
        return data


class WeighingRecord(Base):
    __tablename__ = "balanca_weighing_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(
        Integer,
        ForeignKey("balanca_weighing_tickets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reading_id = Column(Integer, nullable=True, index=True)
    sequencia = Column(Integer, nullable=False)
    tipo = Column(String(24), nullable=False, default="ENTRADA")
    data_hora = Column(DateTime, nullable=False, server_default=SQLSERVER_NOW_UTC_MINUS_3)
    balanca = Column(String(80), nullable=False, default="Balança 002")
    peso = Column(Integer, nullable=False)
    operador = Column(String(120), nullable=False, default="Balança")
    created_at = Column(DateTime, nullable=False, server_default=SQLSERVER_NOW_UTC_MINUS_3)

    ticket = relationship("WeighingTicket", back_populates="weighings")

    def to_dict(self):
        return {
            "id": self.id,
            "ticket_id": self.ticket_id,
            "reading_id": self.reading_id,
            "sequencia": self.sequencia,
            "tipo": self.tipo,
            "data_hora": self.data_hora.isoformat() if self.data_hora else None,
            "balanca": self.balanca,
            "peso": self.peso,
            "operador": _operator_label(self.operador),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class TankPlateCatalog(Base):
    __tablename__ = "balanca_tank_plates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    placa = Column(String(16), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, nullable=False, server_default=SQLSERVER_NOW_UTC_MINUS_3)

    def to_dict(self):
        return {
            "id": self.id,
            "placa": self.placa,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class HorsePlateCatalog(Base):
    __tablename__ = "balanca_horse_plates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    placa = Column(String(16), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, nullable=False, server_default=SQLSERVER_NOW_UTC_MINUS_3)

    def to_dict(self):
        return {
            "id": self.id,
            "placa": self.placa,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class DriverCatalog(Base):
    __tablename__ = "balanca_drivers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(180), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, nullable=False, server_default=SQLSERVER_NOW_UTC_MINUS_3)

    def to_dict(self):
        return {
            "id": self.id,
            "nome": self.nome,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class TransporterCatalog(Base):
    __tablename__ = "balanca_transporters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(180), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, nullable=False, server_default=SQLSERVER_NOW_UTC_MINUS_3)

    def to_dict(self):
        return {
            "id": self.id,
            "nome": self.nome,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class CustomerCatalog(Base):
    __tablename__ = "balanca_customers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(180), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, nullable=False, server_default=SQLSERVER_NOW_UTC_MINUS_3)

    def to_dict(self):
        return {
            "id": self.id,
            "nome": self.nome,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ChemicalSpecCatalog(Base):
    __tablename__ = "balanca_chemical_specs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(180), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, nullable=False, server_default=SQLSERVER_NOW_UTC_MINUS_3)

    def to_dict(self):
        return {
            "id": self.id,
            "nome": self.nome,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class DestinationCatalog(Base):
    __tablename__ = "balanca_destinations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(180), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, nullable=False, server_default=SQLSERVER_NOW_UTC_MINUS_3)

    def to_dict(self):
        return {
            "id": self.id,
            "nome": self.nome,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
