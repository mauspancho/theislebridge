# Native Mod

The native mod target is:

```text
Linux x86_64
ELF shared library .so
UE4SS Linux
Game__Shipping__Linux64
```

The mod uses raw `GUObjectArray` and `NamePool` access. It does not use UE4SS normal UObject iteration, Lua UObject iteration, or `FindFirstOf` for Prime.

IPC request example:

```text
REQUEST_ID=<uuid>
ACTION=PRIME
PLAYER_NAME=maus
```

Result example:

```text
REQUEST_ID=<uuid>
SUCCESS=1
PLAYER=maus
DINOSAUR=BP_Ceratosaurus_C
ELIGIBLE_PRIME=1
PRIME=1
BUILD_SUPPORTED=1
BUILD_ID=cf63a41bf6a6fcbf
```

The file watcher only queues requests. Unreal inspection and `ProcessEvent` execution run from the `GameEngine::Tick` path, hooked through the validated vtable slot `+0x310`, so Prime is not executed from an arbitrary IPC thread.

`ProcessEvent` is called through the real dinosaur vtable slot `+0x268`.
