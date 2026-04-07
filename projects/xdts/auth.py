from __future__ import annotations

import base64
import hashlib
import hmac
import os
from typing import Any


DEFAULT_ALGORITHM = "sha256"
DEFAULT_ITERATIONS = 240_000
SALT_BYTES = 16


def hash_password(
    password: str,
    *,
    algorithm: str = DEFAULT_ALGORITHM,
    iterations: int = DEFAULT_ITERATIONS,
) -> dict[str, Any]:
    if not password:
        raise ValueError("Password must not be empty.")

    salt = os.urandom(SALT_BYTES)
    derived_key = hashlib.pbkdf2_hmac(
        algorithm,
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return {
        "algorithm": algorithm,
        "iterations": iterations,
        "salt": base64.b64encode(salt).decode("ascii"),
        "password_hash": base64.b64encode(derived_key).decode("ascii"),
    }


def verify_password(
    password: str,
    *,
    expected_hash: str,
    salt: str,
    algorithm: str,
    iterations: int,
) -> bool:
    derived_key = hashlib.pbkdf2_hmac(
        algorithm,
        password.encode("utf-8"),
        base64.b64decode(salt.encode("ascii")),
        iterations,
    )
    return hmac.compare_digest(
        base64.b64encode(derived_key).decode("ascii"),
        expected_hash,
    )
