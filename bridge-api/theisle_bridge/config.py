from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass(frozen=True)
class ServerConfig:
    root: str = ""
    binary: str = ""
    binaries_dir: str = ""
    service: str = ""
    build_id: str = ""


@dataclass(frozen=True)
class RconConfig:
    host: str = "127.0.0.1"
    port: int = 8888
    game_ini: str = ""
    timeout_seconds: float = 3.0


@dataclass(frozen=True)
class ApiConfig:
    bind: str = "127.0.0.1"
    port: int = 8765
    token_file: str = "/etc/theisle-server-bridge/token"
    public_health: bool = True


@dataclass(frozen=True)
class NativeConfig:
    runtime_dir: str = "/run/theisle-server-bridge"
    request_timeout_seconds: float = 10.0


@dataclass(frozen=True)
class CompatibilityConfig:
    require_supported_build: bool = True


@dataclass(frozen=True)
class BridgeConfig:
    path: Path
    server: ServerConfig
    rcon: RconConfig
    api: ApiConfig
    native: NativeConfig
    compatibility: CompatibilityConfig


def _section(data: dict, name: str) -> dict:
    value = data.get(name, {})
    return value if isinstance(value, dict) else {}


def load_config(path: str | Path) -> BridgeConfig:
    config_path = Path(path)
    raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    server = ServerConfig(**{**ServerConfig().__dict__, **_section(raw, "server")})
    rcon = RconConfig(**{**RconConfig().__dict__, **_section(raw, "rcon")})
    api = ApiConfig(**{**ApiConfig().__dict__, **_section(raw, "api")})
    native = NativeConfig(**{**NativeConfig().__dict__, **_section(raw, "native")})
    compatibility = CompatibilityConfig(
        **{**CompatibilityConfig().__dict__, **_section(raw, "compatibility")}
    )
    return BridgeConfig(config_path, server, rcon, api, native, compatibility)
