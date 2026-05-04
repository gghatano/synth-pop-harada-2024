# 実験 01: age-change vs age-swap (Murata 2017 §15.1)

## なにを確かめたいか

Murata 2017 §15.1 の主要主張を、本実装で再現できるか確認します。
具体的には、SA（シミュレーテッドアニーリング）の遷移演算子として
`AgeChangeTransition`（1 人の年齢を動かす）と `AgeSwapTransition`
（同じ家族類型・性別の 2 人の年齢を交換）のどちらが優れているかは
`evals_per_agent`（1 人あたりの評価回数）の領域に依存する、という主張です。

- **H1a**: `evals_per_agent` が小さい領域（短時間）では age-change の方が
  best_score が低くなる（Murata 2017 §3 / §5.1）
- **H1b**: `evals_per_agent` が大きい領域では age-swap が逆転して有利になる

## 仮説の評価方法

各 `(seed, evals_per_agent, transition)` で SA を 1 回回し、`best_score`
（21 統計の L1 合計）を記録します。同じ seed × evals 配下で age-change と
age-swap の best_score 差を Wilcoxon signed-rank test で検定し、効果量は
Cliff's δ で表します。

## 入力データ

- 元データ: `data/sample_case/`（リポジトリ同梱のダミー、実際の国勢調査ではない）
- 100 世帯ベースを `paper_results._shared.runner._scale_sample_case` で
  整数倍スケール（`_make_inputs.py` と同じ方式）

## 固定パラメータ

| 項目 | CI 既定 | フル設定 (`--full`) |
|---|---|---|
| seeds | `[1, 2, 3]`（n=3） | `[1..10]`（n=10） |
| `evals_per_agent` | `{500, 2000}` | `{1000, 2000, 4000, 8000, 16000}` |
| 世帯数 | 100 | 1000 |
| 遷移 | `age_change`, `age_swap` | 同左 |
| 目的関数 | strict_extended (Murata 式(3) 21 統計) | 同左 |
| 初期生成 | zero-error init | 同左 |
| 冷却 | `ExponentialCooling(T0=1.0, alpha=0.999)` | 同左 |
| 評価値 CSV | `expected/best_scores.csv`, `expected/stat_l1.csv` | `expected-full/...` |

## 想定実行時間

- CI 既定: 約 4 分（12 runs）
- フル設定: 1〜2 時間（100 runs、`workflow_dispatch` 限定）

## 再現コマンド

```bash
# CI 既定設定で許容幅判定（±1%）
make paper-results-exp01

# expected/*.csv を再生成（手動・レビュー必須）
make paper-results-write   # exp01 + exp02 をまとめて再生成

# フル設定（重実験）
PYTHONPATH=. uv run python paper_results/experiment-01-age-change-vs-age-swap/run.py --full --write-expected
```

## 再現性の指紋（spec §19.3）

期待値 CSV を生成した時点の指紋:

- seed: `[1, 2, 3]`（CI 既定）
- commit_sha: `c045606e50f4999adb6a0b86f39b84bdd4acffc6` (本ディレクトリ初期コミット時点)
- uv_lock_sha256: `dda09efe4af1e31e4f985b2b8b513267f79cfc94dce3856e678347d8def8fa82`

`uv sync --frozen --all-groups` で再現すれば、別マシンでも bitwise 一致する
（spec §19.3）。

## 期待される結果（実測）

CI 既定（n=3 / 100 hh）の実測値:

| seed | evals | age_change | age_swap | swap - change |
|---:|---:|---:|---:|---:|
| 1 | 500 | 453.0 | 567.0 | +114 |
| 1 | 2000 | 453.0 | 567.0 | +114 |
| 2 | 500 | 455.0 | 570.0 | +115 |
| 2 | 2000 | 455.0 | 570.0 | +115 |
| 3 | 500 | 453.0 | 568.0 | +115 |
| 3 | 2000 | 453.0 | 568.0 | +115 |

100 世帯規模では age-change が常に best_score を低く保ち、`evals` を増やしても
age-swap の逆転は観測されません。これは小規模ゆえに age-change が早期に最適に
到達し、`evals` を増やすメリットが乏しいことに整合します。フル設定（1000 世帯）
での H1b 検証は別途 `make paper-results-full` で実施します。
