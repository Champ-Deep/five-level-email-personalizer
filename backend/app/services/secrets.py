"""Symmetric encryption for stored integration credentials.

Uses Fernet (AES-128-CBC + HMAC-SHA256). The key is derived from
JWT_SECRET via SHA-256 → base64url, so rotating the JWT secret
invalidates stored credentials (forcing the user to re-enter API keys,
which is the security behavior we want).
"""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


def _fernet() -> Fernet:
    key = hashlib.sha256(get_settings().jwt_secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_config(config: dict[str, Any]) -> str:
    return _fernet().encrypt(json.dumps(config).encode("utf-8")).decode("ascii")


def decrypt_config(blob: str) -> dict[str, Any]:
    try:
        return json.loads(_fernet().decrypt(blob.encode("ascii")).decode("utf-8"))
    except (InvalidToken, ValueError) as e:
        raise RuntimeError(f"Failed to decrypt stored credential (JWT_SECRET rotated?): {e}") from e
