from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


SECRET_KEYS = {"RconPassword", "ServerPassword", "DedicatedServerClientSecret"}


@dataclass(frozen=True)
class RconSettings:
    enabled: bool
    port: int
    password: str


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def read_key_values(path: str | Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith(("#", ";", "[")):
            continue
        match = re.match(r"^([A-Za-z0-9_.-]+)\s*=\s*(.*)$", line)
        if match:
            values[match.group(1)] = _strip_quotes(match.group(2).split(" //", 1)[0])
    return values


def read_rcon_settings(path: str | Path) -> RconSettings:
    values = read_key_values(path)
    enabled = values.get("bRconEnabled", "false").strip().lower() == "true"
    port_text = values.get("RconPort", "8888")
    try:
        port = int(port_text)
    except ValueError as exc:
        raise ValueError("Invalid RconPort in Game.ini") from exc
    password = values.get("RconPassword", "")
    if enabled and not password:
        raise ValueError("RCON is enabled but RconPassword is empty")
    return RconSettings(enabled=enabled, port=port, password=password)


def sanitized_summary(path: str | Path) -> dict[str, str]:
    values = read_key_values(path)
    return {
        key: ("<redacted>" if key in SECRET_KEYS else value)
        for key, value in values.items()
    }
