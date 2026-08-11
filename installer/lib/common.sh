#!/usr/bin/env bash
set -euo pipefail

PROJECT_NAME="theisle-server-bridge"
INSTALL_DIR="/opt/theisle-server-bridge"
CONFIG_DIR="/etc/theisle-server-bridge"
STATE_DIR="/var/lib/theisle-server-bridge"
LOG_DIR="/var/log/theisle-server-bridge"
RUNTIME_DIR="/run/theisle-server-bridge"
SERVICE_NAME="theisle-server-bridge.service"

log() {
  printf '[%s] %s\n' "$PROJECT_NAME" "$*" >&2
}

fail() {
  printf '[%s] ERROR: %s\n' "$PROJECT_NAME" "$*" >&2
  exit 1
}

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    fail "run this script with sudo"
  fi
}

backup_file() {
  local path="$1"
  if [[ -e "$path" ]]; then
    local stamp
    stamp="$(date +%Y%m%d-%H%M%S)"
    cp -a "$path" "${path}.bak-${stamp}"
    log "backup created: ${path}.bak-${stamp}"
  fi
}

prompt_path() {
  local prompt="$1"
  local value=""
  while [[ -z "$value" ]]; do
    printf '%s ' "$prompt" >&2
    read -r value
  done
  printf '%s\n' "$value"
}

select_candidate() {
  local prompt="$1"
  shift
  local candidates=("$@")
  local choice=""
  log "$prompt"
  local i=1
  for item in "${candidates[@]}"; do
    printf '  %d) %s\n' "$i" "$item" >&2
    i=$((i + 1))
  done
  while true; do
    printf 'Select 1-%d: ' "${#candidates[@]}" >&2
    read -r choice
    if [[ "$choice" =~ ^[0-9]+$ ]] && (( choice >= 1 && choice <= ${#candidates[@]} )); then
      printf '%s\n' "${candidates[$((choice - 1))]}"
      return
    fi
  done
}

read_ini_value() {
  local file="$1"
  local key="$2"
  awk -F= -v key="$key" '
    $1 ~ "^[[:space:]]*" key "[[:space:]]*$" {
      value=$2
      sub(/^[[:space:]]*/, "", value)
      sub(/[[:space:]]*(\/\/.*)?$/, "", value)
      gsub(/^"|"$/, "", value)
      print value
      exit
    }
  ' "$file"
}

detect_build_id() {
  local binary="$1"
  local build_id=""
  build_id="$(readelf -n "$binary" 2>/dev/null | awk '/Build ID:/ {print tolower($3); exit}')"
  if [[ -n "$build_id" ]]; then
    printf '%s\n' "$build_id"
    return
  fi
  file -L "$binary" 2>/dev/null | sed -nE 's/.*BuildID\[[^]]+\]=([0-9A-Fa-f]+).*/\L\1/p' | head -n1
}

safe_install_file() {
  local source="$1"
  local dest="$2"
  local mode="$3"
  local owner="${4:-root:root}"
  install -D -m "$mode" -o "${owner%:*}" -g "${owner#*:}" "$source" "$dest"
}

detect_ue4ss_source() {
  local root="$1"
  local candidates=(
    "${UE4SS_SOURCE_DIR:-}"
    "$root/ue4ss-native-dev"
    "$root/UE4SS"
    "/opt/ue4ss-linux"
  )
  for candidate in "${candidates[@]}"; do
    if [[ -n "$candidate" && -d "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return
    fi
  done
  prompt_path 'Ruta del codigo/fuentes UE4SS disponibles para compilar mods:'
}

build_native_mod() {
  local ue4ss_source="$1"
  local build_dir="$STATE_DIR/build-native"
  local so_path="$build_dir/Game__Shipping__Linux64/lib/libTheIsleBridgeNative.so"
  mkdir -p "$build_dir"
  cmake -S "$REPO_DIR/native-mod" -B "$build_dir" -G Ninja -DCMAKE_BUILD_TYPE=Game__Shipping__Linux64 -DUE4SS_ROOT="$ue4ss_source" >&2
  cmake --build "$build_dir" --target TheIsleBridgeNative -j2 >&2
  printf '%s\n' "$so_path"
}

validate_native_artifact() {
  local so_path="$1"
  [[ -f "$so_path" ]] || fail "native artifact not found: $so_path"
  readelf -h "$so_path" 2>/dev/null | grep -q 'Class:[[:space:]]*ELF64' || fail "native artifact is not ELF64: $so_path"
  readelf -h "$so_path" 2>/dev/null | grep -q 'Machine:[[:space:]]*Advanced Micro Devices X86-64' || fail "native artifact is not x86_64: $so_path"
  readelf -h "$so_path" 2>/dev/null | grep -q 'Type:[[:space:]]*DYN' || fail "native artifact is not a shared object: $so_path"
  nm -D "$so_path" 2>/dev/null | awk '{print $3}' | grep -qx 'start_mod' || fail "native artifact does not export start_mod"
  nm -D "$so_path" 2>/dev/null | awk '{print $3}' | grep -qx 'uninstall_mod' || fail "native artifact does not export uninstall_mod"
  if ! nm -D "$so_path" 2>/dev/null | c++filt | grep -q 'RC::CppUserModBase'; then
    fail "native artifact does not reference RC::CppUserModBase"
  fi
}

install_native_mod() {
  local so_path="$1"
  local mods_dir="$2"
  local mod_dir="$mods_dir/TheIsleBridgeNative"
  validate_native_artifact "$so_path"
  install -d -m 0755 "$mod_dir" "$mod_dir/libs"
  backup_file "$mod_dir/libs/main.so"
  install -m 0755 "$so_path" "$mod_dir/libs/main.so"
  chmod 0755 "$mod_dir" "$mod_dir/libs" "$mod_dir/libs/main.so"
  local mods_txt="$mods_dir/mods.txt"
  touch "$mods_txt"
  backup_file "$mods_txt"
  if grep -Eq '^[[:space:]]*TheIsleBridgeNative[[:space:]]*:' "$mods_txt"; then
    sed -i 's/^[[:space:]]*TheIsleBridgeNative[[:space:]]*:.*/TheIsleBridgeNative : 1/' "$mods_txt"
  else
    printf '\nTheIsleBridgeNative : 1\n' >> "$mods_txt"
  fi
}
