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

It creates backups before replacing bridge files, systemd units, `mods.txt`, or native mod artifacts. It does not reinstall The Isle, delete saves, print RCON passwords, print EOS secrets, or run Prime automatically.

If multiple installations or services are found, the installer asks which one to use. If none is found, it asks only for the root path of the existing The Isle install.
