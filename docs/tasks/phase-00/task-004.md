# task-004: Python 基盤構築（pyproject + uv + ruff + pyright + pre-commit）

## 目的

uv ベースのパッケージング、ruff / pyright の静的検査、pre-commit のコミット時検査、を Phase 1 着手前に「緑の空 CI」が回る最小構成で立ち上げる。以降の実装は常にこの基盤の上で書く。

## 前提・依存

- Python 3.11+ を前提（spec §6.1）。
- パッケージ名 `synthpop_jp` / PyPI 名 `synthpop-jp` 確定（task-003）。
- 3 者レビューで合意: **型チェッカは pyright strict 一本**、mypy は使わない（review-python 推奨ツールチェイン節）。

## 成果物

### a. `/pyproject.toml`

骨子:
```toml
[project]
name = "synthpop-jp"
version = "0.0.0"
description = "Murata 2017 SA-based synthetic population generator with Harada 2024 evaluation."
requires-python = ">=3.11"
license = "Apache-2.0"
readme = "README.md"
dependencies = [
  "pandas>=2.2", "numpy>=2.0", "scipy>=1.13",
  "pydantic>=2.7", "pydantic-settings>=2.3",
  "typer>=0.12", "rich>=13.7",
  "pyyaml>=6.0", "scikit-learn>=1.5", "matplotlib>=3.9",
]

[project.scripts]
synthpop-jp = "synthpop_jp.cli:app"

[project.entry-points."synthpop_jp.evaluators"]
# 外部パッケージからの評価器登録ポイント

[project.entry-points."synthpop_jp.transitions"]
# 外部パッケージからの遷移登録ポイント

[project.entry-points."synthpop_jp.family_types"]
# 外部パッケージからの family_type 登録ポイント

[dependency-groups]
dev = ["pre-commit>=3.7"]
test = ["pytest>=8", "pytest-xdist", "pytest-cov", "pytest-benchmark", "hypothesis>=6.100"]
docs = ["mkdocs-material", "mkdocstrings[python]"]
typing = ["pyright>=1.1.360"]

[tool.uv]
managed = true

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### b. `/uv.lock`

`uv lock` で生成し、リポジトリにコミット（再現性のため。OSS 指摘7）。

### c. `/.ruff.toml` または `pyproject.toml [tool.ruff]`

- `line-length = 100`
- `select = ["E","F","W","I","N","UP","B","SIM","RUF","NPY","PD","PT","D415"]`
- `NPY201` 有効（NumPy 2.x 準拠）
- `[tool.ruff.lint.per-file-ignores]` で `tests/*` の `D` を緩和
- docstring スタイル `numpydoc`

### d. `/pyrightconfig.json`

```json
{
  "include": ["src", "tests"],
  "pythonVersion": "3.11",
  "typeCheckingMode": "strict",
  "reportMissingTypeStubs": "warning",
  "venvPath": ".",
  "venv": ".venv"
}
```

### e. `/.pre-commit-config.yaml`

hooks:
- `ruff` (check + format)
- `pyright`（local hook、`uv run pyright`）
- `check-yaml`
- `check-added-large-files`（`--maxkb=500`）
- `nbstripout`（notebook 混入対策）
- `end-of-file-fixer`

### f. `/.gitignore`

Python / uv / ruff / pyright / pytest / OS (macOS) / editor (VS Code, JetBrains) の標準に加え、`outputs/`, `artifacts/`, `paper_results/tmp/` を除外。

### g. `/Makefile`

ターゲット: `setup`（`uv sync --frozen`）、`lint`（`ruff check`）、`format`（`ruff format`）、`type`（`pyright`）、`test`（`pytest -n auto`）、`bench`（`pytest-benchmark`）、`quickstart`（Phase 1 で埋める、プレースホルダ）、`docs`（Phase 4）、`paper`（Phase 6）。

## 受け入れ基準

- `uv sync --frozen` がエラーなく通る。
- `uv run ruff check .` が 0 件。
- `uv run pyright` が 0 エラー（空実装なのでそもそも警告のみ）。
- `uv run pytest` が collected 0, passed 0 で緑（まだテストが無い状態）。
- `pre-commit run --all-files` が緑。
- `uv.lock` が commit 済み。

## 推定規模

M（半日）。設定ファイル群と uv の初期化。

## 参照

- `docs/reviews/review-python.md` 推奨ツールチェイン節
- `docs/reviews/review-oss.md` 指摘 5, 7
- `docs/reviews/action-plan.md` §2C
