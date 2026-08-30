#!/bin/bash
#
# install.sh - install refree via nix and register a systemd user service
# that starts automatically at boot. Safe to re-run.

set -euo pipefail

app_name="refree"
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"


echo ">>> Building refree via nix..."
REFREE_VENV="$project_dir/.venv" nix build --impure "$project_dir"
refree_bin="$project_dir/result/bin/refree"

config_dir="$HOME/.refree"
config_file="$config_dir/config.yaml"
mkdir -p "$config_dir"
if [[ ! -f "$config_file" ]]; then
    echo ">>> Writing default config to $config_file"
    {
        echo 'refree_dir: "~/.refree/data"'
        echo 'app_host: "127.0.0.1"'
        echo 'app_port: 23119'
    } > "$config_file"
fi

host=$(PYTHONPATH="$project_dir" "$project_dir/.venv/bin/python" -c \
    "from app.common.config import APP_HOST; print(APP_HOST)" 2>/dev/null \
    || echo 127.0.0.1)
port=$(PYTHONPATH="$project_dir" "$project_dir/.venv/bin/python" -c \
    "from app.common.config import APP_PORT; print(APP_PORT)" 2>/dev/null \
    || echo 23119)

if ! command -v systemctl >/dev/null 2>&1; then
    echo ">>> systemd not found; skipping autostart setup." >&2
    echo "    Run manually: $refree_bin" >&2
    exit 0
fi

service_dir="$HOME/.config/systemd/user"
service_file="$service_dir/$app_name.service"
mkdir -p "$service_dir"
echo ">>> Writing systemd user unit to $service_file"
{
    echo "[Unit]"
    echo "Description=refree - self-hosted reference manager"
    echo "After=network.target"
    echo
    echo "[Service]"
    echo "Type=simple"
    echo "ExecStart=$refree_bin"
    echo "Environment=REFREE_CONFIG_FILE=$config_file"
    echo "Restart=on-failure"
    echo "RestartSec=5"
    echo
    echo "[Install]"
    echo "WantedBy=default.target"
} > "$service_file"

loginctl enable-linger "$USER" 2>/dev/null || true

systemctl --user daemon-reload
systemctl --user enable "$app_name.service"
systemctl --user restart "$app_name.service"

echo ">>> $app_name installed and started."
echo "    UI:     http://$host:$port/"
echo "    Health: http://$host:$port/heartbeat"
echo "    Status: systemctl --user status $app_name"
echo "    Logs:   journalctl --user -u $app_name -f"
