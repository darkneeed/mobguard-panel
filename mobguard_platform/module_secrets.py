from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


class ModuleSecretError(ValueError):
    pass


def _fernet(secret_key: str) -> Fernet:
    normalized = str(secret_key or "").strip()
    if not normalized:
        raise ModuleSecretError("MOBGUARD_MODULE_SECRET_KEY is not configured")
    derived_key = base64.urlsafe_b64encode(hashlib.sha256(normalized.encode("utf-8")).digest())
    return Fernet(derived_key)


def encrypt_module_token(secret_key: str, token: str) -> str:
    normalized_token = str(token or "").strip()
    if not normalized_token:
        raise ModuleSecretError("Module token is empty")
    return _fernet(secret_key).encrypt(normalized_token.encode("utf-8")).decode("utf-8")


def decrypt_module_token(secret_key: str, ciphertext: str) -> str:
    normalized_ciphertext = str(ciphertext or "").strip()
    if not normalized_ciphertext:
        raise ModuleSecretError("Module token is unavailable for reveal")
    try:
        return _fernet(secret_key).decrypt(normalized_ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ModuleSecretError("Stored module token cannot be decrypted with the configured secret key") from exc
