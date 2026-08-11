from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bridge-api"))

from theisle_bridge.auth import authorize
from theisle_bridge.build_id import parse_file_build_id, parse_readelf_build_id
from theisle_bridge.build_registry import is_supported_build
from theisle_bridge.commands.prime import PrimeCommandHandler
from theisle_bridge.game_ini import read_rcon_settings, sanitized_summary
from theisle_bridge.ipc import NativeTimeoutError, NativeResult, parse_result, wait_result
from theisle_bridge.native_status import read_native_status
from theisle_bridge.rcon import is_steam_id64, parse_playerlist, resolve_player


class BridgeUnitTests(unittest.TestCase):
    def test_parse_playerlist(self) -> None:
        players = parse_playerlist("PlayerList\n76561198375706611,\nmaus,\n")
        self.assertEqual(len(players), 1)
        self.assertEqual(players[0].steam_id, "76561198375706611")
        self.assertEqual(players[0].name, "maus")

    def test_duplicate_names_are_preserved_for_native_disambiguation(self) -> None:
        players = parse_playerlist("PlayerList\n76561198375706611,\nmaus,\n76561198000000000,\nmaus,\n")
        self.assertEqual([p.name for p in players], ["maus", "maus"])

    def test_offline_player(self) -> None:
        self.assertIsNone(resolve_player([], "76561198375706611"))

    def test_steam_id_validation(self) -> None:
        self.assertTrue(is_steam_id64("76561198375706611"))
        self.assertFalse(is_steam_id64("123"))
        self.assertFalse(is_steam_id64("7656119837570661x"))

    def test_result_parsing_key_value(self) -> None:
        result = parse_result(
            "REQUEST_ID=abc\nSUCCESS=1\nPLAYER=maus\nDINOSAUR=BP_Ceratosaurus_C\n"
            "ELIGIBLE_PRIME=1\nPRIME=1\n"
        )
        self.assertTrue(result.success)
        self.assertEqual(result.dinosaur, "BP_Ceratosaurus_C")
        self.assertTrue(result.eligible_prime)
        self.assertTrue(result.prime)

    def test_result_api_schema(self) -> None:
        body = NativeResult(
            request_id="abc",
            success=True,
            player="maus",
            dinosaur="BP_Ceratosaurus_C",
            eligible_prime=True,
            prime=True,
            already_prime=True,
        ).to_api()
        self.assertEqual(body["success"], True)
        self.assertEqual(body["eligiblePrime"], True)
        self.assertEqual(body["prime"], True)
        self.assertEqual(body["alreadyPrime"], True)

    def test_ipc_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(NativeTimeoutError):
                wait_result(tmp, "missing", 0.01)

    def test_auth(self) -> None:
        self.assertTrue(authorize("Bearer secret", "secret"))
        self.assertFalse(authorize("Bearer wrong", "secret"))
        self.assertFalse(authorize(None, "secret"))

    def test_game_ini_redacts_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Game.ini"
            path.write_text(
                "[/Script/TheIsle.TIGameSession]\n"
                "bRconEnabled=true\n"
                "RconPort=8888\n"
                "RconPassword=\"super-secret\"\n",
                encoding="utf-8",
            )
            settings = read_rcon_settings(path)
            self.assertTrue(settings.enabled)
            self.assertEqual(settings.port, 8888)
            self.assertEqual(settings.password, "super-secret")
            self.assertEqual(sanitized_summary(path)["RconPassword"], "<redacted>")

    def test_build_registry(self) -> None:
        self.assertTrue(is_supported_build("cf63a41bf6a6fcbf"))
        self.assertFalse(is_supported_build("deadbeef"))

    def test_parse_file_xxhash_build_id(self) -> None:
        output = (
            "TheIsleServer-Linux-Shipping: ELF 64-bit LSB executable, x86-64, "
            "BuildID[xxHash]=cf63a41bf6a6fcbf, stripped"
        )
        self.assertEqual(parse_file_build_id(output), "cf63a41bf6a6fcbf")

    def test_parse_file_generic_build_id(self) -> None:
        output = "server: ELF 64-bit LSB executable, BuildID[sha1]=ABCDEF1234, stripped"
        self.assertEqual(parse_file_build_id(output), "abcdef1234")

    def test_parse_readelf_build_id(self) -> None:
        self.assertEqual(parse_readelf_build_id("    Build ID: CF63A41BF6A6FCBF\n"), "cf63a41bf6a6fcbf")

    def test_native_heartbeat_online(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "native.status").write_text(
                f"PID=123\nBUILD_ID=cf63a41bf6a6fcbf\nBUILD_SUPPORTED=1\n"
                f"MOD_VERSION=0.1.1\nTIMESTAMP={time.time()}\n",
                encoding="utf-8",
            )
            with mock.patch("theisle_bridge.native_status.pid_exists", return_value=True):
                status = read_native_status(tmp)
            self.assertTrue(status.online)
            self.assertEqual(status.state, "online")
            self.assertEqual(status.build_id, "cf63a41bf6a6fcbf")
            self.assertTrue(status.build_supported)

    def test_native_heartbeat_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "native.status").write_text(
                "PID=123\nBUILD_ID=cf63a41bf6a6fcbf\nBUILD_SUPPORTED=1\nTIMESTAMP=1\n",
                encoding="utf-8",
            )
            with mock.patch("theisle_bridge.native_status.pid_exists", return_value=True):
                status = read_native_status(tmp, stale_seconds=0.1)
            self.assertFalse(status.online)
            self.assertEqual(status.state, "offline")

    def test_unsupported_build_blocks_prime_before_native_request(self) -> None:
        class FakeRcon:
            def command(self, name: str) -> str:
                raise AssertionError("RCON should not be called for unsupported build writes")

        handler = PrimeCommandHandler(
            FakeRcon(), "/tmp/not-used", 0.01, "deadbeef", require_supported_build=True
        )
        code, body = handler.prime("76561198375706611")
        self.assertEqual(code, 409)
        self.assertEqual(body["error"], "UNSUPPORTED_BUILD")


if __name__ == "__main__":
    unittest.main()
