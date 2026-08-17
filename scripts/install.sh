#!/bin/bash
#
# install.sh - install refree and register it as a systemd user service that
# starts automatically at boot. Safe to re-run.

set -euo pipefail

app_name="refree"
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
venv_dir="$project_dir/.venv"

if ! command -v uv >/dev/null 2>&1; then
    echo ">>> uv not found; installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

echo ">>> Installing dependencies into $venv_dir ..."
uv sync

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

host=$(PYTHONPATH="$project_dir" "$venv_dir/bin/python" -c \
    "from app.common.config import APP_HOST; print(APP_HOST)")
port=$(PYTHONPATH="$project_dir" "$venv_dir/bin/python" -c \
    "from app.common.config import APP_PORT; print(APP_PORT)")

if ! command -v systemctl >/dev/null 2>&1; then
    echo ">>> systemd not found; skipping autostart setup." >&2
    echo "    Run manually: $venv_dir/bin/fastapi run --host $host --port $port" >&2
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
    echo "WorkingDirectory=$project_dir"
    echo "ExecStart=$venv_dir/bin/fastapi run --host $host --port $port"
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
