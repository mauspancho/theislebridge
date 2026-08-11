from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import time


DEFAULT_STALE_SECONDS = 5.0


@dataclass(frozen=True)
class NativeStatus:
    online: bool
    state: str
    pid: int | None = None
    build_id: str = ""
    build_supported: bool = False
    mod_name: str = ""
    mod_version: str = ""
    timestamp: float = 0.0

    def to_health(self) -> dict:
        body = {
            "nativeMod": self.state,
        }
        if self.pid is not None:
            body["nativePid"] = self.pid
        if self.build_id:
            body["nativeBuildId"] = self.build_id
            body["nativeBuildSupported"] = self.build_supported
        if self.mod_version:
            body["nativeModVersion"] = self.mod_version
        return body


def parse_key_value(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def read_native_status(runtime_dir: str | Path, stale_seconds: float = DEFAULT_STALE_SECONDS) -> NativeStatus:
    path = Path(runtime_dir) / "native.status"
    if not path.exists():
        return NativeStatus(online=False, state="unknown")
    try:
        values = parse_key_value(path.read_text(encoding="utf-8", errors="replace"))
        timestamp = float(values.get("TIMESTAMP", "0"))
        pid = int(values.get("PID", "0"))
    except (OSError, ValueError):
        return NativeStatus(online=False, state="unknown")

    if time.time() - timestamp > stale_seconds:
        return NativeStatus(online=False, state="offline", pid=pid, timestamp=timestamp)
    if not pid_exists(pid):
        return NativeStatus(online=False, state="offline", pid=pid, timestamp=timestamp)
    return NativeStatus(
        online=True,
        state="online",
        pid=pid,
        build_id=values.get("BUILD_ID", ""),
        build_supported=values.get("BUILD_SUPPORTED", "").lower() in {"1", "true", "yes"},
        mod_name=values.get("MOD_NAME", ""),
        mod_version=values.get("MOD_VERSION", ""),
        timestamp=timestamp,
    )
