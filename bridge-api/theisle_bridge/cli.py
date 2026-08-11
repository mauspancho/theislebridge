from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .app import run_server
from .build_registry import is_supported_build
from .config import load_config
from .game_ini import read_rcon_settings
from .ipc import runtime_paths
from .rcon import EvrimaRconClient, parse_playerlist


DEFAULT_CONFIG = "/etc/theisle-server-bridge/config.toml"


def doctor(config_path: str) -> int:
    config = load_config(config_path)
    checks: dict[str, object] = {}
    checks["config"] = str(config.path)
    checks["binaryExists"] = Path(config.server.binary).exists()
    checks["buildId"] = config.server.build_id
    checks["buildSupported"] = is_supported_build(config.server.build_id)
    checks["runtimeRequestsExists"] = runtime_paths(config.native.runtime_dir)[0].exists()
    checks["runtimeResultsExists"] = runtime_paths(config.native.runtime_dir)[1].exists()
    try:
        settings = read_rcon_settings(config.rcon.game_ini)
        checks["rconEnabled"] = settings.enabled
        client = EvrimaRconClient(config.rcon.host, config.rcon.port or settings.port, settings.password)
        players = parse_playerlist(client.command("playerlist"))
        checks["rconReachable"] = True
        checks["playersOnline"] = len(players)
    except Exception as exc:
        checks["rconReachable"] = False
        checks["rconError"] = exc.__class__.__name__
    print(json.dumps(checks, indent=2, sort_keys=True))
    return 0 if checks.get("buildSupported") and checks.get("rconReachable") else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="theisle-bridge")
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("serve")
    sub.add_parser("doctor")
    args = parser.parse_args(argv)
    command = args.command or "serve"
    if command == "serve":
        run_server(load_config(args.config))
        return 0
    if command == "doctor":
        return doctor(args.config)
    parser.error(f"Unknown command: {command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
