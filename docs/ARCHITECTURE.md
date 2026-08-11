# Architecture

`theisle-server-bridge` is split into two trust boundaries.

The Python bridge API runs as a normal Debian systemd service. It listens on localhost, authenticates API calls, reads RCON credentials from the existing `Game.ini`, parses `playerlist`, and communicates with the native mod through atomic files under `/run/theisle-server-bridge`.

`TheIsleBridgeNative` runs inside `TheIsleServer-Linux-Shipping` as a UE4SS C++ mod. UE4SS loads it through `start_mod`, owns the returned `RC::CppUserModBase`, calls `on_unreal_init`, and unloads it through `uninstall_mod`.

The mod never exposes raw object pointers to the bridge. It receives only an action, request ID, and player name, then performs raw Unreal discovery inside the game process.

The bridge writes requests under `/run/theisle-server-bridge/requests` and reads results under `/run/theisle-server-bridge/results`. The native mod writes `/run/theisle-server-bridge/native.status` as a heartbeat. `/health` uses that heartbeat instead of directory existence to decide whether the native mod is actually online.

Commands are represented by handlers so future actions can use RCON or UE4SS IPC without changing the public client contract.
