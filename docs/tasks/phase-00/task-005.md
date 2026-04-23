# task-005: GitHub Actions + Issue/PR テンプレ整備

## 目的

CI と release の自動化、Issue/PR の型を提供する。Phase 1 からの PR 運用と v0.1 リリース時の PyPI 公開を一貫して回すための土台。

## 前提・依存

- task-004 の pyproject.toml / uv.lock / ruff / pyright / pytest の各コマンドが成立していること。
- 行動規範は task-003 の `CODE_OF_CONDUCT.md`。

## 成果物

### a. `.github/workflows/ci.yml`

トリガー: push / pull_request。
ジョブ: matrix (Python 3.11 / 3.12) で以下を順に:
1. `astral-sh/setup-uv@v3`
2. `uv sync --frozen`
3. `uv run ruff check`
4. `uv run ruff format --check`
5. `uv run pyright`
6. `uv run pytest -n auto --cov=synthpop_jp --cov-report=xml --cov-fail-under=80`
7. `uv run pytest-benchmark compare`（基準ファイルコミット時のみ、回帰検知）

### b. `.github/workflows/release.yml`

トリガー: tag `v*`。
ジョブ: `uv build` → Trusted Publisher で PyPI に `synthpop-jp` を公開。Zenodo 連携は v0.1 時点では手動でも可（Phase 6 で自動化）。

### c. `.github/ISSUE_TEMPLATE/`

- `bug.yml`（再現手順・期待値・環境）
- `feature.yml`（動機・提案・代替案）
- `new-family-type.yml`（統計出典・role テンプレ・検証データ）
- `new-evaluator.yml`（指標定義・参考文献・既存との違い）

### d. `.github/PULL_REQUEST_TEMPLATE.md`

- 概要 / 変更種別 / テスト観点 / ドキュメント更新 / 関連 Issue / レビュアー向けチェックリスト（spec.md 差分、ADR 追記要否、CHANGELOG 更新要否）

### e. `.github/dependabot.yml`

pip（weekly）, github-actions（weekly）、security alerts 有効。

### f. `.github/discussions/README.md`（Discussions 用、任意）

カテゴリ: Q&A / 新統計データ共有 / 評価器の議論。

## 受け入れ基準

- PR 作成時に `ci.yml` が緑で通る。
- matrix の 3.11 / 3.12 両方で緑。
- Issue テンプレが 4 種ともサイトで選択可能。
- PR テンプレがデフォルト表示される。

## 推定規模

S（半日弱）。定形 YAML が中心。

## 参照

- `docs/reviews/review-oss.md` 指摘 10
- `docs/reviews/action-plan.md` §2C
- `docs/reviews/review-python.md` 推奨ツールチェイン節（CI）
