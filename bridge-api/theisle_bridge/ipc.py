from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import os
import time
import uuid


class NativeTimeoutError(TimeoutError):
    pass


@dataclass(frozen=True)
class NativeResult:
    request_id: str
    success: bool
    error: str = ""
    player: str = ""
    dinosaur: str = ""
    eligible_prime: bool = False
    prime: bool = False
    already_prime: bool = False
    build_supported: bool = False
    build_id: str = ""

    def to_api(self) -> dict:
        body = {
            "success": self.success,
            "player": self.player,
            "dinosaur": self.dinosaur,
            "eligiblePrime": self.eligible_prime,
            "prime": self.prime,
        }
        if self.error:
            body["error"] = self.error
        if self.already_prime:
            body["alreadyPrime"] = True
        if self.build_id:
            body["buildId"] = self.build_id
            body["buildSupported"] = self.build_supported
        return body


def runtime_paths(runtime_dir: str | Path) -> tuple[Path, Path]:
    base = Path(runtime_dir)
    return base / "requests", base / "results"


def ensure_runtime_dirs(runtime_dir: str | Path) -> None:
    requests, results = runtime_paths(runtime_dir)
    requests.mkdir(parents=True, exist_ok=True)
    results.mkdir(parents=True, exist_ok=True)


def write_request(runtime_dir: str | Path, action: str, player_name: str) -> str:
    ensure_runtime_dirs(runtime_dir)
    request_id = str(uuid.uuid4())
    requests, _ = runtime_paths(runtime_dir)
    tmp_path = requests / f"request-{request_id}.tmp"
    final_path = requests / f"request-{request_id}.req"
    payload = {
        "REQUEST_ID": request_id,
        "ACTION": action.upper(),
        "PLAYER_NAME": player_name,
    }
    tmp_path.write_text(
        "\n".join(f"{key}={value}" for key, value in payload.items()) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp_path, final_path)
    return request_id


def wait_result(runtime_dir: str | Path, request_id: str, timeout_seconds: float) -> NativeResult:
    _, results = runtime_paths(runtime_dir)
    deadline = time.monotonic() + timeout_seconds
    result_path = results / f"result-{request_id}.result"
    while time.monotonic() < deadline:
        if result_path.exists():
            result = parse_result(result_path.read_text(encoding="utf-8", errors="replace"))
            archive_path = results / f"result-{request_id}.consumed"
            try:
                os.replace(result_path, archive_path)
            except OSError:
                pass
            return result
        time.sleep(0.05)
    raise NativeTimeoutError(f"Native mod did not answer request {request_id}")


def parse_bool(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "ok"}


def parse_result(text: str) -> NativeResult:
    stripped = text.strip()
    data: dict[str, object]
    if stripped.startswith("{"):
        data = json.loads(stripped)
    else:
        data = {}
        for line in stripped.splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip()
    return NativeResult(
        request_id=str(data.get("requestId") or data.get("REQUEST_ID") or ""),
        success=parse_bool(data.get("success") or data.get("SUCCESS")),
        error=str(data.get("error") or data.get("ERROR") or ""),
        player=str(data.get("player") or data.get("PLAYER") or ""),
        dinosaur=str(data.get("dinosaur") or data.get("DINOSAUR") or ""),
        eligible_prime=parse_bool(data.get("eligiblePrime") or data.get("ELIGIBLE_PRIME")),
        prime=parse_bool(data.get("prime") or data.get("PRIME")),
        already_prime=parse_bool(data.get("alreadyPrime") or data.get("ALREADY_PRIME")),
        build_supported=parse_bool(data.get("buildSupported") or data.get("BUILD_SUPPORTED")),
        build_id=str(data.get("buildId") or data.get("BUILD_ID") or ""),
    )
