# Balanca/security/secrets.py
from __future__ import annotations

import os
import base64
from cryptography.fernet import Fernet, InvalidToken


class SecretError(RuntimeError):
    pass


def get_master_key() -> bytes:
    key_str = os.getenv("BALANCA_MASTER_KEY", "").strip()
    if not key_str:
        raise SecretError(
            "BALANCA_MASTER_KEY não definida. Forneça via variável de ambiente/Secret Manager."
        )

    # valida chave Fernet: base64 url-safe que decodifica para 32 bytes
    try:
        raw = base64.urlsafe_b64decode(key_str.encode("utf-8"))
    except Exception as e:
        raise SecretError("BALANCA_MASTER_KEY inválida (base64 url-safe inválido).") from e

    if len(raw) != 32:
        raise SecretError(
            f"BALANCA_MASTER_KEY inválida: decodifica para {len(raw)} bytes; esperado 32. "
            "Gere com Fernet.generate_key()."
        )

    return key_str.encode("utf-8")


def decrypt(enc_value: str) -> str:
    if not enc_value or not enc_value.strip():
        raise SecretError("Valor criptografado vazio.")

    f = Fernet(get_master_key())
    try:
        plain = f.decrypt(enc_value.strip().encode("utf-8"))
    except InvalidToken as e:
        raise SecretError("Falha ao descriptografar segredo (token inválido/chave incorreta).") from e

    return plain.decode("utf-8")


def encrypt(plain: str) -> str:
    if plain is None:
        raise SecretError("Valor em claro não pode ser None.")

    f = Fernet(get_master_key())
    token = f.encrypt(plain.encode("utf-8"))
    return token.decode("utf-8")
