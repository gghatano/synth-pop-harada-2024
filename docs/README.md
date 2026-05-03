# docs/

`synthpop-jp` のドキュメントを集めるディレクトリです。mkdocs の docs_dir でもあり、`mkdocs build` でこの中身が静的サイトに変換されます（[`mkdocs.yml`](../mkdocs.yml)）。

mkdocs サイトのトップは [`index.md`](index.md)。GitHub から直接見るときの入口は本 README を参照してください。

## まず読む

| 目的 | ファイル |
|---|---|
| いま何ができて何が TODO か | [`status.md`](status.md) |
| 手法と CLI の使い方 | [`guides/how-it-works.md`](guides/how-it-works.md) |
| 開発フロー全体像 | [`getting-started/development-workflow.md`](getting-started/development-workflow.md) |
| データ取り扱いポリシー | [`DATASET.md`](DATASET.md) |

## ディレクトリ構成

| ディレクトリ | 中身 |
|---|---|
| `getting-started/` | 開発フロー全体像（新しく参加する人向けの入口） |
| `guides/` | 「手法と使い方」など読み物 |
| `spec/` | 仕様書群: `spec.md`（全体仕様）/ `data_contract.md`（CSV 列定義）/ `metrics.md`（評価指標）/ `mia_protocol.md`（MIA 事前登録）/ `experiment_report_format.md` |
| `reports/` | 性能ベンチや測定値など、書き換えず追記するスナップショット |
| `rules/` | 開発の遵守事項（Issue 駆動、TDD、worktree、ブランチ戦略、CI parity、文章スタイル など） |
| `templates/` | Issue / 計画 / 実験 / レビューサマリのテンプレート |
| `adr/` | Architecture Decision Records（命名・内部表現・正規化・評価層など、過去の意思決定の根拠） |
| `reviews/` | 3 視点レビュー（Python / Privacy / OSS）と統合 action plan（v0.x 設計判断の経緯記録） |
| `plans/` | 各 Issue の実装計画メモ（着手前に固めた設計の歴史記録） |
| `tasks/` | Phase 0 タスク台帳（プロジェクト初期の作業ブレイクダウン） |
| `papers/` | 参照論文（Murata 2017 / Harada 2024）の関連メモ |

## ドキュメント単独で読めるファイル

| ファイル | 中身 |
|---|---|
| `assumptions.md` | 評価用 real-data protocol、e-Stat 利用規約、統計法 §44 への対応 |
| `experiment_plan.md` | §15 実験の事前登録版（仮説・指標・検定・サンプルサイズ） |
| `DATASET.md` | データ取り扱いポリシーの集約（再配布、出典表示義務、合成ダミーの位置付け） |

## 文章スタイル

技術者でない読者にも追えることを基準にしています。詳細は [`rules/documentation-style.md`](rules/documentation-style.md) を参照してください。

## サイトとして見たい

```bash
uv sync --group docs
uv run mkdocs serve
# http://localhost:8000 を開く
```
