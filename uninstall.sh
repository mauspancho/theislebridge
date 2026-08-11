#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$REPO_DIR/installer/lib/common.sh"

require_root

REMOVE_CONFIG="false"
REMOVE_NATIVE="false"
for arg in "$@"; do
  case "$arg" in
    --remove-config) REMOVE_CONFIG="true" ;;
    --remove-native-mod) REMOVE_NATIVE="true" ;;
    *) fail "unknown option: $arg" ;;
  esac
done

systemctl disable --now "$SERVICE_NAME" 2>/dev/null || true
rm -f "/etc/systemd/system/$SERVICE_NAME"
systemctl daemon-reload
rm -rf "$INSTALL_DIR" "$STATE_DIR" "$LOG_DIR"

if [[ "$REMOVE_CONFIG" == "true" ]]; then
  backup_file "$CONFIG_DIR"
  rm -rf "$CONFIG_DIR"
else
  log "Keeping configuration at $CONFIG_DIR"
fi

if [[ "$REMOVE_NATIVE" == "true" && -f "$CONFIG_DIR/config.toml" ]]; then
  binary="$(awk -F'"' '/^binaries_dir = / {print $2; exit}' "$CONFIG_DIR/config.toml")"
  if [[ -n "$binary" ]]; then
    mod_dir="$binary/Mods/TheIsleBridgeNative"
    backup_file "$mod_dir/libs/main.so"
    rm -rf "$mod_dir"
    log "Removed TheIsleBridgeNative. The Isle saves and configs were not touched."
  fi
else
  log "Keeping native mod unless --remove-native-mod is passed."
fi

log "Uninstall complete. The Isle, saves, Game.ini, Engine.ini, RCON config, UE4SS, and other mods were not removed."
