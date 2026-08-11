# Reverse Engineering Notes

These notes record values validated for the observed The Isle Evrima build. Values in this document are build-specific unless explicitly marked otherwise.

## Supported Build

```text
The Isle Evrima observed: 0.21.784
Engine: Unreal Engine 5.6
ELF: Linux x86_64, stripped, ET_EXEC / non-PIE
Build ID: cf63a41bf6a6fcbf
```

Write operations must fail closed when the Build ID differs.

## Build-Specific Offsets

```text
GEngine = 0xCAE7630
GameEngine::Tick = 0x77517A0
GUObjectArray = 0xC95C600
NamePool = 0xC8A10F0
ProcessEvent virtual slot = +0x268
```

`UObject::ProcessEvent = 0x46B3340` was validated, but Prime calls must use the real dinosaur vtable slot because overrides were observed.

## UE Layouts

The native mod uses the UE5.6 layouts from the task prompt:

```text
UObjectBase ClassPrivate +0x10, NamePrivate +0x18
UStruct SuperStruct +0x40, ChildProperties +0x50
UFunction ParmsSize +0xB6, ReturnValueOffset +0xB8
FField Next +0x18, NamePrivate +0x20
FProperty Offset_Internal +0x44
```

## Prime Struct

`EligiblePrimeElder` is 11 bytes. All bytes must be `0x01` after mutation:

```text
01 01 01 01 01 01 01 01 01 01 01
```

Validated UFunctions:

```text
GetEligiblePrimeElderData: ParmsSize 0xB, ReturnOffset 0x0
SetEligiblePrimeElderData: ParmsSize 0xB, ReturnOffset 0xFFFF
GetIsEligiblePrimeElder: ParmsSize 0x1, ReturnOffset 0x0
IsPrimeElder: ParmsSize 0x1, ReturnOffset 0x0
```

## Player Mapping

Initial identity is:

```text
SteamID64 -> RCON playerlist -> PlayerNamePrivate -> Controller -> PlayerState -> Dino
```

EOS decoding is intentionally deferred.
