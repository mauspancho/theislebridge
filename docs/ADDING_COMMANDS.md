# Adding Commands

New commands should follow:

```text
read
validate
mutate
read-back
verify
```

Add bridge-side orchestration under `bridge-api/theisle_bridge/commands/`. Commands that can be handled by RCON should stay in the bridge. Commands that need Unreal object state should use native IPC and pass only stable identifiers such as player names resolved from SteamID64.

Do not send object pointers, UFunction addresses, or offsets through the API.
