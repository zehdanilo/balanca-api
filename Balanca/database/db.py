from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from ..config import settings

def build_sqlserver_url() -> str:
    # Ex.: mssql+pyodbc://user:pass@host/db?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=yes
    # Atenção: driver precisa estar URL-encoded (espaços viram +)
    driver = settings.SQLSERVER_DRIVER.replace(" ", "+")
    encrypt = settings.SQLSERVER_ENCRYPT
    trust = settings.SQLSERVER_TRUST_CERT

    user = settings.SQLSERVER_USER
    pwd = settings.SQLSERVER_PASSWORD
    host = settings.SQLSERVER_HOST
    db = settings.SQLSERVER_DB

    if not (host and db and user and pwd):
        raise RuntimeError("Config SQL Server incompleta no .env (host/db/user/password).")

    return (
        f"mssql+pyodbc://{user}:{pwd}@{host}/{db}"
        f"?driver={driver}&Encrypt={encrypt}&TrustServerCertificate={trust}"
    )

engine = create_engine(
    build_sqlserver_url(),
    pool_pre_ping=True,
    pool_recycle=3600,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

def init_db():
    from ..models.models import Base
    Base.metadata.create_all(bind=engine)
    _ensure_weighing_ticket_columns()


def _ensure_weighing_ticket_columns():
    inspector = inspect(engine)
    columns = {column["name"].lower() for column in inspector.get_columns("balanca_weighing_tickets")}
    missing_columns = []
    if "tara" not in columns:
        missing_columns.append("ALTER TABLE balanca_weighing_tickets ADD tara INT NULL")
    if "observacao" not in columns:
        missing_columns.append("ALTER TABLE balanca_weighing_tickets ADD observacao NVARCHAR(500) NULL")
    if not missing_columns:
        return

    with engine.begin() as conn:
        for statement in missing_columns:
            conn.execute(text(statement))
