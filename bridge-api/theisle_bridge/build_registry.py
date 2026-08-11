from __future__ import annotations

SUPPORTED_BUILDS = {
    "cf63a41bf6a6fcbf": {
        "game": "The Isle Evrima",
        "observed_version": "0.21.784",
        "engine": "5.6",
        "game_engine_tick": "0x77517A0",
        "g_engine": "0xCAE7630",
        "gu_object_array": "0xC95C600",
        "name_pool": "0xC8A10F0",
        "process_event_slot": "0x268",
    }
}


def is_supported_build(build_id: str | None) -> bool:
    return bool(build_id and build_id.lower() in SUPPORTED_BUILDS)


def build_metadata(build_id: str | None) -> dict:
    if not build_id:
        return {}
    return SUPPORTED_BUILDS.get(build_id.lower(), {})
