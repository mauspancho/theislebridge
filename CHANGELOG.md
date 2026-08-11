# Changelog

## 0.1.1

- Converts `TheIsleBridgeNative` into a real UE4SS C++ mod with `CppUserModBase`, `start_mod`, and `uninstall_mod`.
- Adds native heartbeat status and makes `/health` require a fresh native heartbeat instead of IPC directories.
- Adds Build ID detection fallback for `BuildID[xxHash]=...` from `file -L` and native ELF section-note parsing.
- Fixes installer stdout contamination, token permissions, umask leakage, native mod directory permissions, and native artifact validation.
- Updates `update.sh` to rebuild and install the native mod without restarting The Isle automatically.

## 0.1.0

- Initial repository scaffold for `theisle-server-bridge`.
- Adds Python bridge API, Debian installer scripts, systemd unit, native mod source, tests, and documentation.
