from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import re
import socket
from urllib.parse import urlparse

from .auth import authorize, read_token
from .build_registry import is_supported_build
from .commands import PrimeCommandHandler
from .config import BridgeConfig
from .game_ini import read_rcon_settings
from .ipc import NativeTimeoutError, runtime_paths
from .rcon import EvrimaRconClient, RconError, is_steam_id64


LOG = logging.getLogger("theisle_bridge")


class BridgeHttpServer(ThreadingHTTPServer):
    def __init__(self, config: BridgeConfig):
        self.config = config
        rcon_settings = read_rcon_settings(config.rcon.game_ini)
        self.rcon_settings = rcon_settings
        self.api_token = read_token(config.api.token_file)
        rcon_port = config.rcon.port or rcon_settings.port
        self.rcon = EvrimaRconClient(
            config.rcon.host,
            rcon_port,
            rcon_settings.password,
            config.rcon.timeout_seconds,
        )
        self.prime = PrimeCommandHandler(
            self.rcon,
            config.native.runtime_dir,
            config.native.request_timeout_seconds,
            config.server.build_id,
            config.compatibility.require_supported_build,
        )
        super().__init__((config.api.bind, config.api.port), BridgeHandler)


class BridgeHandler(BaseHTTPRequestHandler):
    server: BridgeHttpServer

    def log_message(self, fmt: str, *args) -> None:
        LOG.info("http client=%s message=%s", self.address_string(), fmt % args)

    def do_GET(self) -> None:
        self._route("GET")

    def do_POST(self) -> None:
        self._route("POST")

    def _route(self, method: str) -> None:
        try:
            path = urlparse(self.path).path
            if path == "/health" and method == "GET":
                self._json(HTTPStatus.OK, self._health())
                return
            if not self._authorized():
                self._json(HTTPStatus.UNAUTHORIZED, {"success": False, "error": "UNAUTHORIZED"})
                return
            if path == "/api/v1/players" and method == "GET":
                self._players()
                return
            match = re.fullmatch(r"/api/v1/players/([^/]+)", path)
            if match and method == "GET":
                self._player(match.group(1))
                return
            match = re.fullmatch(r"/api/v1/players/([^/]+)/prime", path)
            if match and method == "GET":
                self._prime_status(match.group(1))
                return
            if match and method == "POST":
                self._prime_post(match.group(1))
                return
            self._json(HTTPStatus.NOT_FOUND, {"success": False, "error": "NOT_FOUND"})
        except ValueError as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"success": False, "error": str(exc)})
        except NativeTimeoutError:
            self._json(HTTPStatus.GATEWAY_TIMEOUT, {"success": False, "error": "NATIVE_TIMEOUT"})
        except (RconError, OSError, socket.timeout) as exc:
            LOG.warning("request failed error=%s", exc.__class__.__name__)
            self._json(HTTPStatus.BAD_GATEWAY, {"success": False, "error": "RCON_UNAVAILABLE"})
        except Exception:
            LOG.exception("unhandled request failure")
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"success": False, "error": "INTERNAL_ERROR"})

    def _authorized(self) -> bool:
        return authorize(self.headers.get("Authorization"), self.server.api_token)

    def _health(self) -> dict:
        build_supported = is_supported_build(self.server.config.server.build_id)
        rcon_online = False
        try:
            self.server.rcon.command("playerlist")
            rcon_online = True
        except Exception:
            rcon_online = False
        requests, results = runtime_paths(self.server.config.native.runtime_dir)
        native_online = requests.exists() and results.exists()
        return {
            "status": "ok",
            "gameServer": "unknown",
            "rcon": "online" if rcon_online else "offline",
            "nativeMod": "online" if native_online else "unknown",
            "buildSupported": build_supported,
            "buildId": self.server.config.server.build_id,
        }

    def _players(self) -> None:
        players = self.server.prime.players()
        self._json(
            HTTPStatus.OK,
            {"players": [{"steamId": p.steam_id, "name": p.name, "online": True} for p in players]},
        )

    def _player(self, steam_id: str) -> None:
        if not is_steam_id64(steam_id):
            self._json(HTTPStatus.BAD_REQUEST, {"success": False, "error": "INVALID_STEAM_ID"})
            return
        player = self.server.prime.player_by_steam_id(steam_id)
        if player is None:
            self._json(HTTPStatus.NOT_FOUND, {"success": False, "error": "PLAYER_OFFLINE"})
            return
        self._json(HTTPStatus.OK, {"steamId": player.steam_id, "name": player.name, "online": True})

    def _prime_status(self, steam_id: str) -> None:
        if not is_steam_id64(steam_id):
            self._json(HTTPStatus.BAD_REQUEST, {"success": False, "error": "INVALID_STEAM_ID"})
            return
        code, body = self.server.prime.status(steam_id)
        self._json(code, body)

    def _prime_post(self, steam_id: str) -> None:
        if not is_steam_id64(steam_id):
            self._json(HTTPStatus.BAD_REQUEST, {"success": False, "error": "INVALID_STEAM_ID"})
            return
        code, body = self.server.prime.prime(steam_id)
        self._json(code, body)

    def _json(self, status: int, body: dict) -> None:
        payload = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def run_server(config: BridgeConfig) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    server = BridgeHttpServer(config)
    LOG.info("bridge listening bind=%s port=%s", config.api.bind, config.api.port)
    server.serve_forever()
