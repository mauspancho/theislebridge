# theisle-server-bridge

Local REST bridge for administering an existing The Isle Evrima dedicated server on Debian Linux.

Milestone 1 focuses on one validated action: enable Prime Elder for the dinosaur currently controlled by an online player resolved by SteamID64.

## Architecture

```text
Discord or Web backend
        |
        | HTTP REST on 127.0.0.1:8765
        v
theisle-server-bridge
        |
        | RCON playerlist + local file IPC
        v
TheIsleBridgeNative UE4SS native mod
        |
        v
The Isle Evrima server process
```

The bridge owns RCON, authentication, request timeouts, and JSON responses. The native mod owns Unreal memory inspection and Prime mutation. Pointers never leave the game process.

## Supported Target

- Debian Linux x86_64.
- UE4SS Linux native mod loaded into `TheIsleServer-Linux-Shipping`.
- Final native artifact is an ELF shared library: `TheIsleBridgeNative/libs/main.so`.
- Windows is used only to author the repository. The `.so` is built on Debian by `install.sh`.

The current write-capable build registry supports only:

```text
Build ID: cf63a41bf6a6fcbf
Engine: UE 5.6
Game version observed: 0.21.784
```

If the server binary Build ID does not match, health/status can still run, but write operations are rejected.

## Install On Debian

Clone this repository on the Debian server where The Isle is already installed, then run:

```bash
sudo ./install.sh
```

The installer detects the existing game installation, UE4SS, `Game.ini`, optional systemd unit, Build ID, and UE4SS mod directory. It never reinstalls The Isle and never deletes saves. Any file it changes is backed up first.

Default paths created:

```text
/opt/theisle-server-bridge
/etc/theisle-server-bridge
/var/lib/theisle-server-bridge
/var/log/theisle-server-bridge
/run/theisle-server-bridge
```

The API binds to `127.0.0.1:8765` by default.

## API

```http
GET  /health
GET  /api/v1/players
GET  /api/v1/players/{steamId}
GET  /api/v1/players/{steamId}/prime
POST /api/v1/players/{steamId}/prime
```

`/health` is public on localhost by default. `/api/v1/*` requires:

```http
Authorization: Bearer <token>
```

The token is generated during installation and stored outside git at:

```text
/etc/theisle-server-bridge/token
```

## Smoke Tests

Read-only:

```bash
curl http://127.0.0.1:8765/health
TOKEN="$(sudo cat /etc/theisle-server-bridge/token)"
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8765/api/v1/players
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8765/api/v1/players/<steamId>/prime
```

Manual Prime test, never run automatically by the installer:

```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:8765/api/v1/players/<steamId>/prime
```

## Safety Rules

- No RCON password, EOS secret, bearer token, or raw pointer is logged or returned by the API.
- Write operations require a supported Build ID.
- Prime uses read, validate, mutate, read-back, verify.
- The bridge service is separate from the The Isle service; restarting the bridge does not restart the game.
- `PrimeProbeNative` should remain untouched until `TheIsleBridgeNative` has been validated on the real server.

More detail lives in `docs/`.
