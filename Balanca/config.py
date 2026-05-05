from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

from Balanca.security.secrets import decrypt, SecretError  # ajuste o import conforme seu layout


def _get_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    v = v.strip().lower()
    return v in ("1", "true", "yes", "y", "on")


def _get_int(name: str, default: int) -> int:
    v = os.getenv(name)
    if v is None or not v.strip():
        return default
    return int(v)


def _get_float(name: str, default: float) -> float:
    v = os.getenv(name)
    if v is None or not v.strip():
        return default
    return float(v)


def _get_secret_plain(
    *, enc_env_name: str, legacy_plain_env_name: str | None = None, required: bool = True
) -> str:
    enc = os.getenv(enc_env_name, "").strip()
    if enc:
        return decrypt(enc)

    if legacy_plain_env_name:
        legacy = os.getenv(legacy_plain_env_name, "").strip()
        if legacy:
            return legacy

    if required:
        raise RuntimeError(
            f"Segredo ausente: defina {enc_env_name} (criptografado) "
            f"{'ou ' + legacy_plain_env_name + ' (legado)' if legacy_plain_env_name else ''}."
        )
    return ""


@dataclass(frozen=True)
class Settings:
    # Flask
    APP_HOST: str
    APP_PORT: int
    FLASK_DEBUG: bool

    # TCP / P03
    TCP_IP: str
    TCP_PORT: int
    TCP_TIMEOUT_S: float
    CS_OPTIONAL: bool
    CS_REQUIRED: bool

    # SQL Server
    SQLSERVER_HOST: str
    SQLSERVER_DB: str
    SQLSERVER_USER: str
    SQLSERVER_PASSWORD: str
    SQLSERVER_DRIVER: str
    SQLSERVER_ENCRYPT: str
    SQLSERVER_TRUST_CERT: str

    # Logging
    LOG_LEVEL: str
    LOG_API_ACCESS: bool

    # Reader tuning
    RECONNECT_BACKOFF_S: str

    API_AUTH_ENABLED: bool
    API_USERNAME: str
    API_PASSWORD: str
    CONTROL_LOCALHOST_ONLY: bool

    AUTO_START_READER: bool = True
    AUTO_START_DELAY_S: float = 1.0

    # -----------------------------
    # NOVO: agendamento interno de persistência
    # -----------------------------
    AUTO_PERSIST_LATEST: bool = True
    AUTO_PERSIST_INTERVAL_S: float = 300.0  # 5 min


def _load_settings() -> Settings:
    try:
        sql_pwd = _get_secret_plain(
            enc_env_name="SQLSERVER_PASSWORD_ENC",
            legacy_plain_env_name="SQLSERVER_PASSWORD",
            required=True,
        )

        api_pwd = _get_secret_plain(
            enc_env_name="API_PASSWORD_ENC",
            legacy_plain_env_name="API_PASSWORD",
            required=_get_bool("API_AUTH_ENABLED", True),
        )

    except SecretError as e:
        raise RuntimeError(f"Falha de segredos: {e}") from e

    return Settings(
        APP_HOST=os.getenv("APP_HOST", "0.0.0.0"),
        APP_PORT=_get_int("APP_PORT", 5000),
        FLASK_DEBUG=_get_bool("FLASK_DEBUG", False),

        TCP_IP=os.getenv("TCP_IP", "192.168.0.50"),
        TCP_PORT=_get_int("TCP_PORT", 9001),
        TCP_TIMEOUT_S=_get_float("TCP_TIMEOUT_S", 5.0),

        CS_OPTIONAL=_get_bool("CS_OPTIONAL", True),
        CS_REQUIRED=_get_bool("CS_REQUIRED", False),

        SQLSERVER_HOST=os.getenv("SQLSERVER_HOST", ""),
        SQLSERVER_DB=os.getenv("SQLSERVER_DB", ""),
        SQLSERVER_USER=os.getenv("SQLSERVER_USER", ""),
        SQLSERVER_PASSWORD=sql_pwd,
        SQLSERVER_DRIVER=os.getenv("SQLSERVER_DRIVER", "ODBC Driver 18 for SQL Server"),
        SQLSERVER_ENCRYPT=os.getenv("SQLSERVER_ENCRYPT", "yes"),
        SQLSERVER_TRUST_CERT=os.getenv("SQLSERVER_TRUST_CERT", "yes"),

        LOG_LEVEL=os.getenv("LOG_LEVEL", "INFO"),
        LOG_API_ACCESS=_get_bool("LOG_API_ACCESS", True),

        RECONNECT_BACKOFF_S=os.getenv("RECONNECT_BACKOFF_S", "1,2,5,10,30"),

        API_AUTH_ENABLED=_get_bool("API_AUTH_ENABLED", True),
        API_USERNAME=os.getenv("API_USERNAME", "admin"),
        API_PASSWORD=api_pwd,
        CONTROL_LOCALHOST_ONLY=_get_bool("CONTROL_LOCALHOST_ONLY", False),

        AUTO_START_READER=_get_bool("AUTO_START_READER", True),
        AUTO_START_DELAY_S=_get_float("AUTO_START_DELAY_S", 1.0),

        AUTO_PERSIST_LATEST=_get_bool("AUTO_PERSIST_LATEST", True),
        AUTO_PERSIST_INTERVAL_S=_get_float("AUTO_PERSIST_INTERVAL_S", 300.0),
    )


settings = _load_settings()
