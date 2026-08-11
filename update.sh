#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$REPO_DIR/installer/lib/common.sh"

require_root
[[ -d "$REPO_DIR/.git" ]] || fail "update.sh must be run from a git clone"
[[ -f "$CONFIG_DIR/config.toml" ]] || fail "missing $CONFIG_DIR/config.toml; run install.sh first"

command -v python3 >/dev/null || fail "python3 is required"
command -v cmake >/dev/null || fail "cmake is required"
command -v ninja >/dev/null || fail "ninja-build is required"
command -v readelf >/dev/null || fail "binutils/readelf is required"
command -v nm >/dev/null || fail "binutils/nm is required"
command -v c++filt >/dev/null || fail "binutils/c++filt is required"
command -v rsync >/dev/null || fail "rsync is required"

config_value() {
  local key="$1"
  awk -F'"' -v key="$key" '$0 ~ "^[[:space:]]*" key "[[:space:]]*=" {print $2; exit}' "$CONFIG_DIR/config.toml"
}

root="$(config_value root)"
binaries_dir="$(config_value binaries_dir)"
[[ -n "$root" ]] || fail "server.root missing from config"
[[ -n "$binaries_dir" ]] || fail "server.binaries_dir missing from config"

log "Running read-only unit tests"
python3 -m unittest discover -s "$REPO_DIR/tests" -p 'test_*.py'

ue4ss_source="$(detect_ue4ss_source "$root")"
[[ -d "$ue4ss_source" ]] || fail "UE4SS source directory not found"
mods_dir="$binaries_dir/Mods"
native_so="$(build_native_mod "$ue4ss_source")"
install_native_mod "$native_so" "$mods_dir"
log "Native mod updated; restart the The Isle service to load the new .so."

log "Updating bridge files"
rsync -a --delete "$REPO_DIR/bridge-api/theisle_bridge" "$INSTALL_DIR/"
"$INSTALL_DIR/venv/bin/python" -m compileall -q "$INSTALL_DIR/theisle_bridge"

log "Restarting bridge service only"
systemctl restart "$SERVICE_NAME"

log "The Isle was not restarted automatically."
