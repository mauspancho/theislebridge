#!/usr/bin/env bash
set -euo pipefail

CONFIG="${1:-/etc/theisle-server-bridge/config.toml}"
exec /opt/theisle-server-bridge/venv/bin/python -m theisle_bridge --config "$CONFIG" doctor
