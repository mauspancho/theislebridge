from __future__ import annotations

from dataclasses import dataclass
import re
import socket
from typing import Iterable


COMMANDS = {
    "announce": 0x10,
    "directmessage": 0x11,
    "serverdetails": 0x12,
    "wipecorpses": 0x13,
    "getplayables": 0x14,
    "updateplayables": 0x15,
    "togglemigrations": 0x19,
    "ban": 0x20,
    "kick": 0x30,
    "playerlist": 0x40,
    "save": 0x50,
    "pause": 0x60,
    "getplayerdata": 0x77,
    "togglewhitelist": 0x81,
    "addwhitelist": 0x82,
    "removewhitelist": 0x83,
    "toggleglobalchat": 0x84,
    "togglehumans": 0x86,
    "toggleai": 0x90,
    "disableaiclasses": 0x91,
    "aidensity": 0x92,
    "getqueuestatus": 0x93,
    "toggleailearning": 0x94,
    "custom": 0x70,
}


class RconError(RuntimeError):
    pass


@dataclass(frozen=True)
class Player:
    steam_id: str
    name: str
    online: bool = True


def is_steam_id64(value: str) -> bool:
    return bool(re.fullmatch(r"7656[0-9]{13}", value))


class EvrimaRconClient:
    def __init__(self, host: str, port: int, password: str, timeout: float = 3.0):
        self.host = host
        self.port = int(port)
        self.password = password
        self.timeout = float(timeout)

    def command(self, name: str, data: str = "") -> str:
        command = name.lower()
        if command not in COMMANDS:
            raise ValueError(f"Unsupported RCON command: {name}")
        with socket.create_connection((self.host, self.port), timeout=self.timeout) as sock:
            sock.settimeout(self.timeout)
            self._send(sock, b"\x01" + self.password.encode("utf-8") + b"\x00")
            auth_response = self._recv(sock)
            if "Password Accepted" not in auth_response:
                raise RconError("RCON authentication failed")
            payload = bytes([0x02, COMMANDS[command]]) + data.encode("utf-8") + b"\x00"
            self._send(sock, payload)
            return self._recv(sock)

    @staticmethod
    def _send(sock: socket.socket, payload: bytes) -> None:
        sock.sendall(payload)

    def _recv(self, sock: socket.socket) -> str:
        chunks: list[bytes] = []
        while True:
            try:
                chunk = sock.recv(65535)
            except TimeoutError:
                break
            except socket.timeout:
                break
            if not chunk:
                break
            chunks.append(chunk)
            if len(chunk) < 65535:
                break
        raw = b"".join(chunks)
        return raw.replace(b"\x03", b"").replace(b"\x00", b"").decode("utf-8", "replace")


def parse_playerlist(text: str) -> list[Player]:
    lines = [line.strip().strip(",") for line in text.splitlines()]
    tokens = [token.strip() for line in lines for token in line.split(",") if token.strip()]
    if tokens and tokens[0].lower() == "playerlist":
        tokens = tokens[1:]
    players: list[Player] = []
    i = 0
    while i < len(tokens):
        steam_id = tokens[i]
        name = tokens[i + 1] if i + 1 < len(tokens) else ""
        if is_steam_id64(steam_id) and name:
            players.append(Player(steam_id=steam_id, name=name))
            i += 2
        else:
            i += 1
    return players


def resolve_player(players: Iterable[Player], steam_id: str) -> Player | None:
    if not is_steam_id64(steam_id):
        raise ValueError("INVALID_STEAM_ID")
    matches = [player for player in players if player.steam_id == steam_id]
    return matches[0] if matches else None
