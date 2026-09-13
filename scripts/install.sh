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
mcp_bin="$project_dir/result/bin/refree-mcp"

# Install both binaries to a PATH directory so any client (the web service,
# any MCP-capable agent, a shell) can launch them by name, independent of
# the project source path or any agent-specific config directory.
local_bin_dir="$HOME/.local/bin"
mkdir -p "$local_bin_dir"
ln -sfn "$refree_bin" "$local_bin_dir/$app_name"
ln -sfn "$mcp_bin" "$local_bin_dir/refree-mcp"

# Register the MCP server definition. The content is the standard,
# agent-agnostic `mcpServers` JSON shape; the file location is the pi-mcp-adapter
# global config, read automatically by pi. Any other MCP client can consume the
# same snippet from its own config file.
mcp_config="${REFREE_MCP_CONFIG:-$HOME/.pi/agent/mcp.json}"
mkdir -p "$(dirname "$mcp_config")"
"$project_dir/.venv/bin/python" - "$mcp_config" "$local_bin_dir/refree-mcp" <<'PY'
import json
import os
import sys

path, command = sys.argv[1], sys.argv[2]
try:
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
except FileNotFoundError:
    data = {}
except json.JSONDecodeError:
    os.replace(path, path + ".bak")
    data = {}
if not isinstance(data, dict):
    data = {}
servers = data.setdefault("mcpServers", {})
servers["refree"] = {"command": command}
with open(path, "w", encoding="utf-8") as handle:
    json.dump(data, handle, indent=2)
    handle.write("\n")
PY

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
echo
echo ">>> MCP server (agent-agnostic, stdio):"
echo "    Installed on PATH: refree-mcp -> $local_bin_dir/refree-mcp"
echo "    Server definition registered in: $mcp_config"
echo "    (standard mcpServers JSON; pi-mcp-adapter loads it automatically.)"
echo "    Build the search index first with:"
echo "      $project_dir/.venv/bin/python $project_dir/scripts/index_papers.py"
