# Debian Install

Run on the Debian x86_64 server after The Isle is already installed:

```bash
sudo ./install.sh
```

The installer detects:

- `TheIsleServer-Linux-Shipping`
- `TheIsle/Binaries/Linux`
- `Mods`
- `Game.ini`
- optional existing The Isle systemd unit
- UE4SS runtime
- UE4SS source directory
- Build ID

Build ID detection first tries `readelf -n` and then falls back to `file -L` output like:

```text
BuildID[xxHash]=cf63a41bf6a6fcbf
```

It creates backups before replacing bridge files, systemd units, `mods.txt`, or native mod artifacts. It does not reinstall The Isle, delete saves, print RCON passwords, print EOS secrets, or run Prime automatically.

If multiple installations or services are found, the installer asks which one to use. If none is found, it asks only for the root path of the existing The Isle install.

## UE4SS_ROOT

The native mod is compiled against the UE4SS source tree using:

```bash
cmake -DUE4SS_ROOT=<path>
```

The installer checks `UE4SS_SOURCE_DIR`, common install paths under the The Isle root, and `/opt/ue4ss-linux`. If none is found, it asks for the path.

## Permissions

The API token is:

```text
/etc/theisle-server-bridge/token
owner: root:theisle-bridge
mode: 0640
```

The native mod install path is:

```text
Mods/TheIsleBridgeNative       0755
Mods/TheIsleBridgeNative/libs  0755
Mods/TheIsleBridgeNative/libs/main.so 0755
```

The game service user is added to group `theisle-bridge` when the installer can detect it. Restart The Isle after install so the process loads the new `.so` and picks up group membership.

## Updates

Run:

```bash
sudo ./update.sh
```

`update.sh` runs tests, rebuilds and validates `TheIsleBridgeNative`, installs `main.so`, and restarts only `theisle-server-bridge.service`. It does not restart The Isle automatically. Restart the The Isle service manually when you are ready for the game process to load the new `.so`.
