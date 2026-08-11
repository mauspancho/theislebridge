from __future__ import annotations

from dataclasses import dataclass

from .. import ipc
from ..build_registry import is_supported_build
from ..rcon import EvrimaRconClient, Player, resolve_player


@dataclass
class PrimeCommandHandler:
    rcon: EvrimaRconClient
    runtime_dir: str
    request_timeout_seconds: float
    build_id: str
    require_supported_build: bool = True

    def players(self) -> list[Player]:
        return self.rcon_playerlist()

    def rcon_playerlist(self) -> list[Player]:
        from ..rcon import parse_playerlist

        return parse_playerlist(self.rcon.command("playerlist"))

    def player_by_steam_id(self, steam_id: str) -> Player | None:
        return resolve_player(self.rcon_playerlist(), steam_id)

    def status(self, steam_id: str) -> tuple[int, dict]:
        player = self.player_by_steam_id(steam_id)
        if player is None:
            return 404, {"success": False, "error": "PLAYER_OFFLINE", "steamId": steam_id}
        result = self._native("STATUS", player.name)
        body = result.to_api()
        body.update({"steamId": steam_id, "player": player.name, "online": True})
        return (200 if result.success else 409), body

    def prime(self, steam_id: str) -> tuple[int, dict]:
        if self.require_supported_build and not is_supported_build(self.build_id):
            return 409, {
                "success": False,
                "error": "UNSUPPORTED_BUILD",
                "steamId": steam_id,
                "buildId": self.build_id,
            }
        player = self.player_by_steam_id(steam_id)
        if player is None:
            return 404, {"success": False, "error": "PLAYER_OFFLINE", "steamId": steam_id}
        result = self._native("PRIME", player.name)
        body = result.to_api()
        body.update({"steamId": steam_id, "player": player.name, "online": True})
        return (200 if result.success else 409), body

    def _native(self, action: str, player_name: str) -> ipc.NativeResult:
        request_id = ipc.write_request(self.runtime_dir, action, player_name)
        return ipc.wait_result(self.runtime_dir, request_id, self.request_timeout_seconds)
