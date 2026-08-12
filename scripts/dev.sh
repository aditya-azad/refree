#!/bin/bash

set -euo pipefail

session_name="refree"
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
zellij d "$session_name" >/dev/null 2>&1 || true

env_script="$(mktemp)"
trap 'rm -f "$env_script"' EXIT
cat > "$env_script" <<SH
#!/bin/bash
[[ -f "$project_dir/.venv/bin/activate" ]] && source "$project_dir/.venv/bin/activate"
[[ -f "$project_dir/.env" ]] && { set -a; source "$project_dir/.env"; set +a; }
eval "\$*"
SH
chmod +x "$env_script"

layout=$(cat <<'KDL'
layout {
    cwd "PROJECT_DIR"

    default_tab_template {
        pane size=1 borderless=true {
            plugin location="zellij:tab-bar"
        }
        children
        pane size=2 borderless=true {
            plugin location="zellij:status-bar"
        }
    }

    pane_template name="dev" command="ENV_SCRIPT" {}

    tab name="editor" focus=true {
        dev name="editor" {
            cwd "PROJECT_DIR"
            args "nvim"
        }
    }

    tab name="dev" split_direction="horizontal" {
        dev name="fastapi" {
            args "alembic upgrade head && fastapi dev --port \"${APP_PORT:-8000}\""
        }
        dev name="openpanel" {
            args "cd openpanel && docker compose -p refree-dev-openpanel --env-file \"PROJECT_DIR/.env\" up"
        }
    }
}
pane_frames true
KDL
)

layout="${layout//PROJECT_DIR/$project_dir}"
layout="${layout//ENV_SCRIPT/$env_script}"

zellij --layout-string "$layout" attach "$session_name" -c
