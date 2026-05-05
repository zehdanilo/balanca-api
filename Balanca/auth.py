import base64
from functools import wraps
from typing import Callable, Any, Optional, Tuple

from flask import request, jsonify, Response, g
from Balanca.config import settings


def _unauthorized() -> Response:
    # WWW-Authenticate faz o cliente entender que é Basic Auth
    resp = jsonify({"ok": False, "error": {"message": "Não autorizado"}})
    resp.status_code = 401
    resp.headers["WWW-Authenticate"] = 'Basic realm="BALANCA API"'
    return resp


def _parse_basic_auth(header: str) -> Optional[Tuple[str, str]]:
    """
    header: 'Basic base64(user:pass)'
    retorna (user, pass) ou None
    """
    try:
        if not header:
            return None
        parts = header.split(" ", 1)
        if len(parts) != 2 or parts[0].lower() != "basic":
            return None
        raw = base64.b64decode(parts[1]).decode("utf-8", errors="strict")
        if ":" not in raw:
            return None
        user, pwd = raw.split(":", 1)
        return user, pwd
    except Exception:
        return None


def require_auth(fn: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(fn)
    def wrapper(*args, **kwargs):
        # se auth estiver desabilitado, libera (útil em dev)
        if not settings.API_AUTH_ENABLED:
            g.auth_user = ""
            return fn(*args, **kwargs)

        header = request.headers.get("Authorization", "")
        creds = _parse_basic_auth(header)
        if not creds:
            return _unauthorized()

        user, pwd = creds

        if user != settings.API_USERNAME or pwd != settings.API_PASSWORD:
            return _unauthorized()

        g.auth_user = user

        # Opcional: travar /start e /stop só para localhost
        if settings.CONTROL_LOCALHOST_ONLY and request.path in ("/start", "/stop"):
            ip = (request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
                  or request.remote_addr
                  or "")
            if ip not in ("127.0.0.1", "::1"):
                return jsonify({"ok": False, "error": {"message": "Controle permitido apenas via localhost"}}), 403

        return fn(*args, **kwargs)

    return wrapper
