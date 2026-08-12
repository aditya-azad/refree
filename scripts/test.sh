#!/bin/bash

set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$project_dir/.venv/bin/activate"

set -a
source "$project_dir/.env.test"
set +a

cd "$project_dir"

echo ">>> Running alembic migrations..."
alembic upgrade head

echo ">>> Running pytests..."
if [ $# -gt 0 ]; then
    pytest -s "$@"
else
    pytest -s "$project_dir"
fi

echo "All tests passed."
