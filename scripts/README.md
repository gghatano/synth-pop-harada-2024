# scripts/

`synthpop-jp` 本体には含めない、開発・運用補助のスクリプトを置きます。すべて `uv run python scripts/<name>.py` で実行できます。

## ファイル一覧

| ファイル | 役割 |
|---|---|
| `generate_sample_case.py` | `data/sample_case/` の 7 本の CSV を seed 固定で再生成する。同梱ダミーのスキーマを変えたいときに使う |
| `check_cadence.py` | uncommitted 変更の規模を測り、閾値超過なら exit 1 する。`make cadence` から呼ばれ、commit cadence を物理的に強制する（[`docs/rules/`](../docs/rules/) の cadence ルール参照） |
| `merge_pr.py` | `make merge-pr PR=N` の実体。PR を ready→merge→worktree 削除→develop 同期まで 1 コマンドで実行する |
| `pm_status.py` | 並列 Agent の進捗ダッシュボード。`make pm` から呼ばれ、active worktree・heavy 実験・open PR を 1 画面に出す |

## 設計方針

- `synthpop-jp` の CLI とは独立。本体パッケージに依存しない補助スクリプト
- 各スクリプトは単体で実行可能（標準 lib + 必要最小限の依存のみ）
- 失敗時は exit code を返して Makefile / CI から判定可能にする
- 対応するテストは [`tests/scripts/`](../tests/scripts/) を参照

## 構想中の追加

- `fetch_estat.py` — e-Stat 実データの取り込み配管（[Issue #103](https://github.com/gghatano/synth-pop-harada-2024/issues/103)）
