#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$REPO_DIR/installer/lib/common.sh"

SUPPORTED_BUILD_ID="cf63a41bf6a6fcbf"

detect_binary() {
  mapfile -t binaries < <(
    find /home /opt /srv /steam /var -path '*/TheIsle/Binaries/Linux/TheIsleServer-Linux-Shipping' -type f 2>/dev/null | sort -u
  )
  if (( ${#binaries[@]} == 1 )); then
    printf '%s\n' "${binaries[0]}"
  elif (( ${#binaries[@]} > 1 )); then
    select_candidate "Multiple The Isle server binaries found:" "${binaries[@]}"
  else
    local root
    root="$(prompt_path 'Ruta raiz de la instalacion existente de The Isle:')"
    local candidate="$root/TheIsle/Binaries/Linux/TheIsleServer-Linux-Shipping"
    [[ -f "$candidate" ]] || fail "server binary not found at $candidate"
    printf '%s\n' "$candidate"
  fi
}

detect_service() {
  local binary="$1"
  mapfile -t units < <(systemctl list-unit-files --type=service --no-legend 2>/dev/null | awk '{print $1}' | grep -Ei 'theisle|evrima' || true)
  local matches=()
  for unit in "${units[@]}"; do
    local fragment
    fragment="$(systemctl show -p FragmentPath --value "$unit" 2>/dev/null || true)"
    if [[ -n "$fragment" && -f "$fragment" ]] && grep -Fq "$binary" "$fragment"; then
      matches+=("$unit")
    fi
  done
  if (( ${#matches[@]} == 1 )); then
    printf '%s\n' "${matches[0]}"
  elif (( ${#matches[@]} > 1 )); then
    select_candidate "Multiple matching The Isle services found:" "${matches[@]}"
  elif (( ${#units[@]} == 1 )); then
    printf '%s\n' "${units[0]}"
  elif (( ${#units[@]} > 1 )); then
    select_candidate "Possible The Isle services found:" "${units[@]}"
  else
    printf '\n'
  fi
}

detect_game_ini() {
  local root="$1"
  local candidate="$root/TheIsle/Saved/Config/LinuxServer/Game.ini"
  if [[ -f "$candidate" ]]; then
    printf '%s\n' "$candidate"
    return
  fi
  mapfile -t configs < <(find "$root" -path '*/LinuxServer/Game.ini' -type f 2>/dev/null | sort -u)
  if (( ${#configs[@]} == 1 )); then
    printf '%s\n' "${configs[0]}"
  elif (( ${#configs[@]} > 1 )); then
    select_candidate "Multiple Game.ini files found:" "${configs[@]}"
  else
    fail "Game.ini not found under $root"
  fi
}

ensure_user() {
  if ! getent group theisle-bridge >/dev/null; then
    groupadd --system theisle-bridge
  fi
  if ! id -u theisle-bridge >/dev/null 2>&1; then
    useradd --system --no-create-home --gid theisle-bridge --home-dir "$INSTALL_DIR" --shell /usr/sbin/nologin theisle-bridge
  fi
}

grant_runtime_access_to_game_user() {
  local service="$1"
  local game_user=""
  if [[ -n "$service" ]]; then
    game_user="$(systemctl show -p User --value "$service" 2>/dev/null || true)"
  fi
  if [[ -n "$game_user" && "$game_user" != "root" ]]; then
    usermod -a -G theisle-bridge "$game_user"
    log "Added game service user '$game_user' to group theisle-bridge for IPC access"
  elif [[ "$game_user" == "root" ]]; then
    log "The Isle service runs as root; IPC access is already available"
  else
    log "Could not detect The Isle service user. Add the game process user to group 'theisle-bridge' if native IPC cannot write to $RUNTIME_DIR."
  fi
}

grant_game_ini_read_access() {
  local game_ini="$1"
  if command -v setfacl >/dev/null; then
    setfacl -m u:theisle-bridge:r "$game_ini"
    log "Granted read access to Game.ini using ACL"
  else
    log "setfacl not found. Ensure user 'theisle-bridge' can read Game.ini without exposing secrets broadly."
  fi
}

write_config() {
  local root="$1"
  local binary="$2"
  local binaries_dir="$3"
  local service="$4"
  local build_id="$5"
  local game_ini="$6"
  local rcon_port="$7"
  local config_path="$CONFIG_DIR/config.toml"
  backup_file "$config_path"
  cat > "$config_path" <<EOF_CONFIG
[server]
root = "$root"
binary = "$binary"
binaries_dir = "$binaries_dir"
service = "$service"
build_id = "$build_id"

[rcon]
host = "127.0.0.1"
port = $rcon_port
game_ini = "$game_ini"
timeout_seconds = 3.0

[api]
bind = "127.0.0.1"
port = 8765
token_file = "$CONFIG_DIR/token"
public_health = true

[native]
runtime_dir = "$RUNTIME_DIR"
request_timeout_seconds = 10.0

[compatibility]
require_supported_build = true
EOF_CONFIG
  chmod 0640 "$config_path"
  chown root:theisle-bridge "$config_path"
}

main() {
  require_root
  [[ -f /etc/debian_version ]] || fail "this installer targets Debian"
  [[ "$(uname -m)" == "x86_64" ]] || fail "this installer targets x86_64"

  command -v python3 >/dev/null || fail "python3 is required"
  command -v cmake >/dev/null || fail "cmake is required"
  command -v ninja >/dev/null || fail "ninja-build is required"
  command -v readelf >/dev/null || fail "binutils/readelf is required"
  command -v nm >/dev/null || fail "binutils/nm is required"
  command -v c++filt >/dev/null || fail "binutils/c++filt is required"
  command -v file >/dev/null || fail "file is required"
  command -v rsync >/dev/null || fail "rsync is required"
  command -v curl >/dev/null || fail "curl is required"

  local binary binaries_dir root build_id service game_ini rcon_enabled rcon_port ue4ss_runtime ue4ss_source native_so mods_dir
  binary="$(detect_binary)"
  binaries_dir="$(dirname "$binary")"
  root="${binary%/TheIsle/Binaries/Linux/TheIsleServer-Linux-Shipping}"
  build_id="$(detect_build_id "$binary")"
  [[ -n "$build_id" ]] || fail "could not read Build ID from $binary"
  service="$(detect_service "$binary")"
  game_ini="$(detect_game_ini "$root")"
  rcon_enabled="$(read_ini_value "$game_ini" bRconEnabled)"
  rcon_port="$(read_ini_value "$game_ini" RconPort)"
  [[ "${rcon_enabled,,}" == "true" ]] || fail "RCON is not enabled in Game.ini"
  [[ -n "$rcon_port" ]] || rcon_port="8888"
  ue4ss_runtime="$binaries_dir/libUE4SS.so"
  [[ -f "$ue4ss_runtime" ]] || fail "UE4SS runtime not found at $ue4ss_runtime"
  ue4ss_source="$(detect_ue4ss_source "$root")"
  [[ -d "$ue4ss_source" ]] || fail "UE4SS source directory not found"
  mods_dir="$binaries_dir/Mods"
  mkdir -p "$mods_dir"

  log "The Isle root: $root"
  log "Server binary: $binary"
  log "Build ID: $build_id"
  if [[ "$build_id" != "$SUPPORTED_BUILD_ID" ]]; then
    log "Build is unsupported for write operations. Prime POST will be disabled."
  fi
  [[ -n "$service" ]] && log "Detected service: $service"
  log "Game.ini detected. RCON port: $rcon_port"
  log "UE4SS runtime: $ue4ss_runtime"
  log "UE4SS source: $ue4ss_source"

  ensure_user
  grant_runtime_access_to_game_user "$service"
  install -d -m 0755 "$INSTALL_DIR" "$STATE_DIR" "$LOG_DIR"
  install -d -m 0750 -o root -g theisle-bridge "$CONFIG_DIR"
  install -d -m 0770 -o theisle-bridge -g theisle-bridge "$RUNTIME_DIR" "$RUNTIME_DIR/requests" "$RUNTIME_DIR/results"

  rsync -a --delete "$REPO_DIR/bridge-api/theisle_bridge" "$INSTALL_DIR/"
  python3 -m venv "$INSTALL_DIR/venv"
  "$INSTALL_DIR/venv/bin/python" -m compileall -q "$INSTALL_DIR/theisle_bridge"

  if [[ ! -f "$CONFIG_DIR/token" ]]; then
    (
      umask 077
      python3 - <<'PY' > "$CONFIG_DIR/token"
import secrets
print(secrets.token_urlsafe(32))
PY
    )
  fi
  chown root:theisle-bridge "$CONFIG_DIR/token"
  chmod 0640 "$CONFIG_DIR/token"

  write_config "$root" "$binary" "$binaries_dir" "$service" "$build_id" "$game_ini" "$rcon_port"
  grant_game_ini_read_access "$game_ini"
  native_so="$(build_native_mod "$ue4ss_source")"
  install_native_mod "$native_so" "$mods_dir"

  safe_install_file "$REPO_DIR/systemd/$SERVICE_NAME" "/etc/systemd/system/$SERVICE_NAME" 0644 root:root
  systemctl daemon-reload
  systemctl enable --now "$SERVICE_NAME"

  "$INSTALL_DIR/venv/bin/python" -m unittest discover -s "$REPO_DIR/tests" -p 'test_*.py'
  sleep 1
  curl -fsS "http://127.0.0.1:8765/health" >/dev/null || log "health check did not respond yet; inspect with scripts/doctor.sh"

  log "Install complete. Secrets were not printed."
  log "Read-only checks:"
  printf '  curl http://127.0.0.1:8765/health\n'
  printf '  TOKEN="$(sudo cat %s/token)"\n' "$CONFIG_DIR"
  printf '  curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8765/api/v1/players\n'
  log "Manual Prime test, only after a player is online and status was reviewed:"
  printf '  curl -X POST -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8765/api/v1/players/<steamId>/prime\n'
}

main "$@"
