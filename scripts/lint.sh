#!/bin/bash

set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$project_dir/.venv/bin/activate"

echo ">>> Running pyrefly..."
pyrefly check "$project_dir/app"

echo ">>> Running ruff format..."
ruff format "$project_dir/app"

echo ">>> Running ruff check (--fix)..."
ruff check --config "$project_dir/pyproject.toml" --fix "$project_dir/app"

echo ">>> Suppression line counts..."
declare -A suppressions=(
  ["noqa"]="noqa"
  ["type: ignore"]="type: ignore"
  ["mypy: ignore"]="mypy: ignore"
  ["pyright: ignore"]="pyright: ignore"
  ["pylint: disable"]="pylint: disable"
  ["isort: skip"]="isort: skip"
  ["bandit"]="bandit"
  ["pragma: no cover"]="pragma: no cover"
)
total=0
details=()
for label in "${!suppressions[@]}"; do
  pattern="${suppressions[$label]}"
  mapfile -t matches < <(grep -rn --include="*.py" "$pattern" "$project_dir/app" || true)
  count="${#matches[@]}"
  printf "%s: %s\n" "$label" "$count"
  total=$(( total + count ))
  for line in "${matches[@]}"; do
    details+=("$label | $line")
  done
done
echo "total: $total"
if [ "$total" -gt 0 ]; then
  echo "--- details ---"
  for line in "${details[@]}"; do
    echo "$line"
  done
fi

echo "All checks passed."
