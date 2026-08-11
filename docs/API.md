# API

Base URL:

```text
http://127.0.0.1:8765
```

All `/api/v1/*` endpoints require `Authorization: Bearer <token>`.

## GET /health

Read-only. Does not require auth by default.

`nativeMod` is `online` only when the native mod heartbeat is fresh and its reported PID exists. The endpoint may also include:

```json
{
  "nativePid": 1234,
  "nativeBuildId": "cf63a41bf6a6fcbf",
  "nativeBuildSupported": true,
  "nativeModVersion": "0.1.1"
}
```

RCON and native mod health are independent because RCON can be offline while The Isle is still starting.

## GET /api/v1/players

Uses RCON `playerlist` and returns online players as SteamID64 plus player name.

## GET /api/v1/players/{steamId}

Returns one online player or `PLAYER_OFFLINE`.

## GET /api/v1/players/{steamId}/prime

Read-only. Resolves SteamID64 through RCON, asks the native mod for current Prime status by player name, and returns dinosaur plus eligibility flags.

## POST /api/v1/players/{steamId}/prime

Write operation. Requires a supported Build ID. The native mod resolves the current dinosaur on every request, checks current state, writes the 11 Prime bytes only when needed, then verifies by read-back and boolean UFunctions.
