#!/usr/bin/env bash
# Re-run experiments/ entries filtered by WEIGHT.md (Issue #115 Step 5).
#
# Usage:
#   scripts/run_experiments_by_weight.sh light  # WEIGHT.md == "light" のみ
#   scripts/run_experiments_by_weight.sh heavy  # WEIGHT.md == "heavy" のみ
#   scripts/run_experiments_by_weight.sh all    # 全部
#
# CI からは light のみ呼ぶ前提（heavy は workflow_dispatch / 手元実行向け）。

set -euo pipefail

WEIGHT="${1:-light}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EXP_ROOT="$REPO_ROOT/experiments"

if [[ ! -d "$EXP_ROOT" ]]; then
    echo "experiments/ not found: $EXP_ROOT" >&2
    exit 1
fi

declare -i ran=0
declare -i skipped=0

for dir in "$EXP_ROOT"/*/; do
    [[ -d "$dir" ]] || continue
    weight_file="$dir/WEIGHT.md"
    if [[ ! -f "$weight_file" ]]; then
        echo "[skip] no WEIGHT.md: $dir" >&2
        skipped+=1
        continue
    fi
    actual_weight="$(head -n1 "$weight_file" | tr -d '[:space:]')"
    if [[ "$WEIGHT" != "all" && "$actual_weight" != "$WEIGHT" ]]; then
        echo "[skip] weight=$actual_weight (want $WEIGHT): $dir" >&2
        skipped+=1
        continue
    fi
    run_py="$dir/run.py"
    if [[ ! -f "$run_py" ]]; then
        echo "[skip] no run.py: $dir" >&2
        skipped+=1
        continue
    fi
    echo "[run] $run_py"
    (cd "$REPO_ROOT" && uv run python "$run_py")
    ran+=1
done

echo "Done: ran=$ran skipped=$skipped (weight filter: $WEIGHT)"
