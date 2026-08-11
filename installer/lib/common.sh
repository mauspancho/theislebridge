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
  printf '[%s] %s\n' "$PROJECT_NAME" "$*"
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
    read -r -p "$prompt " value
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
    printf '  %d) %s\n' "$i" "$item"
    i=$((i + 1))
  done
  while true; do
    read -r -p "Select 1-${#candidates[@]}: " choice
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
  readelf -n "$binary" 2>/dev/null | awk '/Build ID:/ {print $3; exit}'
}

safe_install_file() {
  local source="$1"
  local dest="$2"
  local mode="$3"
  local owner="${4:-root:root}"
  install -D -m "$mode" -o "${owner%:*}" -g "${owner#*:}" "$source" "$dest"
}
