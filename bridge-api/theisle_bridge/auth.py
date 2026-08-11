from __future__ import annotations

from hmac import compare_digest
from pathlib import Path


def read_token(path: str) -> str:
    token = Path(path).read_text(encoding="utf-8").strip()
    if not token:
        raise ValueError("API token file is empty")
    return token


def authorize(header_value: str | None, token: str) -> bool:
    if not header_value:
        return False
    scheme, _, value = header_value.partition(" ")
    return scheme.lower() == "bearer" and compare_digest(value.strip(), token)
