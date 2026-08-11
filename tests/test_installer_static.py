from __future__ import annotations

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class InstallerStaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.common = (ROOT / "installer" / "lib" / "common.sh").read_text(encoding="utf-8")
        cls.install = (ROOT / "install.sh").read_text(encoding="utf-8")
        cls.cmake = (ROOT / "native-mod" / "CMakeLists.txt").read_text(encoding="utf-8")
        cls.native = (ROOT / "native-mod" / "TheIsleBridgeNative" / "src" / "main.cpp").read_text(
            encoding="utf-8"
        )

    def test_select_candidate_prompts_do_not_contaminate_stdout(self) -> None:
        body = self._function_body(self.common, "select_candidate")
        self.assertIn('log "$prompt"', body)
        self.assertIn('>&2', body)
        self.assertRegex(body, r"printf '%s\\n' \"\$\{candidates")

    def test_build_id_falls_back_to_file_buildid(self) -> None:
        body = self._function_body(self.common, "detect_build_id")
        self.assertIn("readelf -n", body)
        self.assertIn("file -L", body)
        self.assertIn("BuildID\\[[^]]+\\]", body)

    def test_build_native_mod_stdout_is_only_artifact_path(self) -> None:
        body = self._function_body(self.common, "build_native_mod")
        self.assertIn("cmake -S", body)
        self.assertIn(">&2", body)
        self.assertRegex(body, r"printf '%s\\n' \"\$so_path\"")

    def test_native_artifact_validation_checks_ue4ss_exports(self) -> None:
        body = self._function_body(self.common, "validate_native_artifact")
        self.assertIn("start_mod", body)
        self.assertIn("uninstall_mod", body)
        self.assertIn("RC::CppUserModBase", body)
        self.assertIn("ELF64", body)

    def test_token_permissions_are_group_readable_not_world_readable(self) -> None:
        self.assertIn('chown root:theisle-bridge "$CONFIG_DIR/token"', self.install)
        self.assertIn('chmod 0640 "$CONFIG_DIR/token"', self.install)
        self.assertNotIn("umask 077\n    python3", self.install)

    def test_native_mod_directories_are_0755(self) -> None:
        body = self._function_body(self.common, "install_native_mod")
        self.assertIn('install -d -m 0755 "$mod_dir" "$mod_dir/libs"', body)
        self.assertIn('install -m 0755 "$so_path" "$mod_dir/libs/main.so"', body)

    def test_cmake_uses_ue4ss_root(self) -> None:
        self.assertIn("UE4SS_ROOT is required", self.cmake)
        self.assertIn('add_subdirectory("${UE4SS_ROOT}"', self.cmake)
        self.assertIn("target_link_libraries(${TARGET} PUBLIC UE4SS)", self.cmake)

    def test_native_exports_ue4ss_lifecycle(self) -> None:
        self.assertIn("#include <Mod/CppUserModBase.hpp>", self.native)
        self.assertIn("public RC::CppUserModBase", self.native)
        self.assertIn("start_mod()", self.native)
        self.assertIn("uninstall_mod(RC::CppUserModBase* mod)", self.native)
        self.assertIn("on_unreal_init()", self.native)

    @staticmethod
    def _function_body(text: str, name: str) -> str:
        match = re.search(rf"^{name}\(\) \{{\n(?P<body>.*?)\n\}}", text, re.MULTILINE | re.DOTALL)
        if not match:
            raise AssertionError(f"function not found: {name}")
        return match.group("body")


if __name__ == "__main__":
    unittest.main()
