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

.PHONY: help setup lint format type test bench quickstart docs paper all

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
	uv run pytest --benchmark-only

quickstart:
	uv run synthpop-jp quickstart

docs:
	@echo "[Phase 4] mkdocs build — not yet implemented"
	@exit 1

paper:
	@echo "[Phase 6] paper_results reproduction — not yet implemented"
	@exit 1

all: lint format type test
