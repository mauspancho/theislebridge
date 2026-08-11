#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$REPO_DIR/installer/lib/common.sh"

require_root
[[ -d "$REPO_DIR/.git" ]] || fail "update.sh must be run from a git clone"

log "Running read-only unit tests"
python3 -m unittest discover -s "$REPO_DIR/tests" -p 'test_*.py'

log "Updating bridge files"
rsync -a --delete "$REPO_DIR/bridge-api/theisle_bridge" "$INSTALL_DIR/"
"$INSTALL_DIR/venv/bin/python" -m compileall -q "$INSTALL_DIR/theisle_bridge"

if [[ -f "$CONFIG_DIR/config.toml" ]]; then
  log "Restarting bridge service only"
  systemctl restart "$SERVICE_NAME"
else
  fail "missing $CONFIG_DIR/config.toml; run install.sh first"
fi

log "Native mod updates require rebuilding and then restarting The Isle manually so the new .so can be loaded."
