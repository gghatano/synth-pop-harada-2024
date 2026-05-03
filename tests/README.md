# tests/

`synthpop-jp` のテストスイート。本体ソース [`src/synthpop_jp/`](../src/synthpop_jp/) のディレクトリ構成と対応するように切ってあります。

## レイアウト

| ディレクトリ | 対応する src モジュール |
|---|---|
| `cli/` | `cli.py` のサブコマンド統合テスト |
| `compare/` | `compare/` の比較 runner と統計検定 |
| `domain/` | `domain/`（Protocol、距離、ドメインモデル） |
| `evaluate/` | `evaluate/`（aggregate / rare / utility / privacy / CAP） |
| `init/` | `init/`（初期人口生成、9 family types カバレッジ） |
| `io/` | `io/`（pydantic ローダ、writer、再構築） |
| `optimize/` | `optimize/`（SA runner、遷移、目的関数、checkpoint、trace） |
| `reports/` | `reports/`（markdown / HTML / plot 生成） |
| `scripts/` | `scripts/`（cadence checker、PR helper など補助スクリプト） |
| `unit/` | 横断的な単体テスト |
| `integration/` | 複数モジュールをまたぐ統合テスト |
| `property/` | hypothesis property test（差分更新と再計算の整合性、不変条件） |
| `regression/` | 回帰テスト（許容幅 ±1% の挙動と決定性 bitwise 一致） |
| `benchmarks/` | pytest-benchmark（SA 性能ゲート、smoke 版が CI で毎 PR 走る） |

## 共通

- `conftest.py` — fixture 集約
- `test_imports.py` — 全モジュールが import 可能なことのスモークテスト

## 走らせ方

```bash
# 全部
uv run pytest

# benchmark のみ（手動）
uv run pytest tests/benchmarks --benchmark-only

# CI parity 4 検査（push 前推奨）
make ci
```

## 設計原則

- TDD: 新しい振る舞いには「落ちるテスト」を先に書く（[`docs/rules/tdd.md`](../docs/rules/tdd.md)）
- 決定性: 同 seed で bitwise 一致を `regression/` で保証する
- property test: 差分更新と全再計算の一致は `property/` で hypothesis に任せる
- benchmark: 性能ゲートは `tests/benchmarks/` に閉じる（CI smoke は軽量、本格版は `make bench` で手動）
