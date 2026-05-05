from sqlalchemy import create_engine
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
