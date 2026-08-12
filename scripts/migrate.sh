#!/bin/bash

set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$project_dir/.venv/bin/activate"



usage() {
    cat <<'USAGE'
Usage: scripts/migrate.sh <command> [args]

Commands:
  upgrade [target]      Apply migrations (default: head).
  downgrade [target]    Roll back migrations (default: -1, one revision).
  create <message>      Generate a new autogenerate revision with the given message.
  current               Show the current migration revision.
  history               Show the migration history.
USAGE
}

cmd="${1:-}"
if [[ -z "$cmd" ]]; then
    usage
    exit 1
fi
shift

# alembic.ini lives in the project root, so run from there.
cd "$project_dir"

case "$cmd" in
    upgrade)
        target="${1:-head}"
        echo ">>> Upgrading database to ${target}..."
        alembic upgrade "$target"
        echo ">>> Done."
        ;;
    downgrade)
        target="${1:--1}"
        echo ">>> Downgrading database by ${target}..."
        alembic downgrade "$target"
        echo ">>> Done."
        ;;
    create)
        message="${1:-}"
        if [[ -z "$message" ]]; then
            echo "Error: 'create' requires a migration message."
            echo "  scripts/migrate.sh create \"add foo table\""
            exit 1
        fi
        echo ">>> Generating autogenerate revision: ${message}..."
        alembic revision --autogenerate -m "$message"
        echo ">>> Done. Review the generated file before applying."
        ;;
    current)
        alembic current
        ;;
    history)
        alembic history --verbose
        ;;
    *)
        usage
        exit 1
        ;;
esac
