# TheIsleBridgeNative

UE4SS native mod for The Isle Evrima Linux.

The Debian installer builds this target as an ELF `.so` and installs it as:

```text
TheIsle/Binaries/Linux/Mods/TheIsleBridgeNative/libs/main.so
```

The mod intentionally avoids normal UE4SS UObject iteration. It uses the validated raw `GUObjectArray` and `NamePool` path for the supported Build ID.
