from __future__ import annotations

import re


BUILD_ID_RE = re.compile(r"BuildID\[[^\]]+\]=([0-9A-Fa-f]+)")
GNU_BUILD_ID_RE = re.compile(r"Build ID:\s*([0-9A-Fa-f]+)")


def parse_file_build_id(output: str) -> str:
    match = BUILD_ID_RE.search(output)
    return match.group(1).lower() if match else ""


def parse_readelf_build_id(output: str) -> str:
    match = GNU_BUILD_ID_RE.search(output)
    return match.group(1).lower() if match else ""
