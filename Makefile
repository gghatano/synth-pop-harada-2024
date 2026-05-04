# synthpop-jp — developer task runner
#
# 使い方:
#   make setup       # uv sync --frozen で開発環境を構築
#   make lint        # ruff check
#   make format      # ruff format
#   make type        # pyright strict
#   make test        # pytest -n auto
#   make bench       # pytest-benchmark
#   make quickstart  # Phase 1 で実装（synthpop-jp quickstart）
#   make docs        # Phase 4 で実装（mkdocs build）
#   make paper       # Phase 6 で実装（paper_results 再現）
#   make pm          # PM status ダッシュボード（並列 Agent 進捗確認）

.PHONY: help setup lint format type test bench quickstart docs paper pm all \
        paper-results paper-results-exp01 paper-results-exp02 \
        paper-results-exp03 paper-results-exp04 paper-results-write \
        paper-results-full repro-experiments audit-experiments

help:
	@echo "Available targets:"
	@echo "  setup       Install locked dependencies via uv sync --frozen"
	@echo "  lint        Run ruff check"
	@echo "  format      Run ruff format"
	@echo "  type        Run pyright (strict)"
	@echo "  test        Run pytest -n auto"
	@echo "  bench       Run pytest-benchmark (Phase 2+)"
	@echo "  quickstart  Run synthpop-jp quickstart (Phase 1)"
	@echo "  docs        Build mkdocs site (Phase 4)"
	@echo "  paper       Reproduce paper_results (Phase 6)"
	@echo "  pm          PM status dashboard (parallel Agent monitoring)"

setup:
	uv sync --frozen

lint:
	uv run ruff check .

format:
	uv run ruff format .

type:
	uv run pyright

test:
	uv run pytest -n auto

bench:
	uv run pytest tests/benchmarks/ -m benchmark --benchmark-only

quickstart:
	uv run synthpop-jp quickstart

docs:
	uv run mkdocs build

docs-serve:
	uv run mkdocs serve

# --- paper_results 再現ターゲット (Issue #115 / #121) ---
# `make paper-results` で実験 01 / 02 / 03 / 04 を CI 既定設定で再実行し、
# expected/*.csv に対する許容幅判定（spec §19.4 ±1%）を行う。
# 期待値の更新は `make paper-results-write` を手動で走らせる。
# フル設定（spec §15.1 / §15.2 凍結値）は `make paper-results-full`。

paper-results: paper-results-exp01 paper-results-exp02 paper-results-exp03 paper-results-exp04

paper-results-exp01:
	PYTHONPATH=. uv run python paper_results/experiment-01-age-change-vs-age-swap/run.py --check-tolerance

paper-results-exp02:
	PYTHONPATH=. uv run python paper_results/experiment-02-hybrid-strategy/run.py --check-tolerance

paper-results-exp03:
	PYTHONPATH=. uv run python paper_results/experiment-03-improve-strategy-comparison/run.py --check-tolerance

paper-results-exp04:
	PYTHONPATH=. uv run python paper_results/experiment-04-multi-trial-variance/run.py --check-tolerance

paper-results-write:
	PYTHONPATH=. uv run python paper_results/experiment-01-age-change-vs-age-swap/run.py --write-expected
	PYTHONPATH=. uv run python paper_results/experiment-02-hybrid-strategy/run.py --write-expected
	PYTHONPATH=. uv run python paper_results/experiment-03-improve-strategy-comparison/run.py --write-expected
	PYTHONPATH=. uv run python paper_results/experiment-04-multi-trial-variance/run.py --write-expected

paper-results-full:
	PYTHONPATH=. uv run python paper_results/experiment-01-age-change-vs-age-swap/run.py --full --check-tolerance
	PYTHONPATH=. uv run python paper_results/experiment-02-hybrid-strategy/run.py --full --check-tolerance
	PYTHONPATH=. uv run python paper_results/experiment-03-improve-strategy-comparison/run.py --check-tolerance
	PYTHONPATH=. uv run python paper_results/experiment-04-multi-trial-variance/run.py --check-tolerance

# 旧 paper: ターゲットの後方互換エイリアス。
paper: paper-results

repro-experiments:
	@bash scripts/run_experiments_by_weight.sh light

audit-experiments:
	uv run python scripts/audit_experiments.py

.PHONY: pm
pm:
	uv run python scripts/pm_status.py $(ARGS)

all: lint format type test

.PHONY: cadence
cadence:
	uv run python scripts/check_cadence.py $(ARGS)

.PHONY: merge-pr
merge-pr:
	@if [ -z "$(PR)" ]; then echo "Usage: make merge-pr PR=<number> [DRY_RUN=1]"; exit 1; fi
	uv run python scripts/merge_pr.py --pr $(PR) $(if $(DRY_RUN),--dry-run,)
