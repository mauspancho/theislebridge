# Native Mod

The native mod target is:

```text
Linux x86_64
ELF shared library .so
UE4SS Linux
Game__Shipping__Linux64
```

The mod uses raw `GUObjectArray` and `NamePool` access. It does not use UE4SS normal UObject iteration, Lua UObject iteration, or `FindFirstOf` for Prime.

`TheIsleBridgeNative` is a real UE4SS C++ mod. It derives from:

```cpp
RC::CppUserModBase
```

and exports Linux-visible lifecycle functions:

```cpp
extern "C" RC::CppUserModBase* start_mod();
extern "C" void uninstall_mod(RC::CppUserModBase* mod);
```

UE4SS starts the worker from `on_unreal_init()` and stops it from the mod destructor. The implementation does not rely on ELF constructor/destructor functions as its primary lifecycle.

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

## Build ID

The native mod detects the currently loaded `/proc/self/exe` every time it starts. It parses GNU build-id notes from both program headers and section headers, including 8-byte note payloads that `file -L` reports as:

```text
BuildID[xxHash]=cf63a41bf6a6fcbf
```

The mod remains fail-closed. Unsupported or unknown Build ID means no Prime write.

## Heartbeat

While loaded, the mod writes:

```text
/run/theisle-server-bridge/native.status
```

The status contains only non-secret fields:

```text
PID=<The Isle PID>
BUILD_ID=<id>
BUILD_SUPPORTED=0|1
MOD_NAME=TheIsleBridgeNative
MOD_VERSION=<version>
TIMESTAMP=<epoch seconds>
```

The bridge API considers the native mod online only when this heartbeat is recent and the PID still exists.

## Verification

After build/install:

```bash
nm -D Mods/TheIsleBridgeNative/libs/main.so | c++filt | grep -E 'start_mod|uninstall_mod|CppUserModBase'
grep TheIsleBridgeNative TheIsle/Binaries/Linux/UE4SS.log
grep TheIsleBridgeNative /proc/<TheIsle PID>/maps
curl http://127.0.0.1:8765/health
```
