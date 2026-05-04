# 実験 04: 複数候補ばらつきの定量化

## なにを確かめたいか

改善ループ（spec §14）は **同じ設定でも seed が違えば異なる候補列を出す** はずです。本実験は rule_based 戦略を 1 つに固定し、**5 つの seed × n_trials=5 の合計 25 試行** を走らせて、各 trial の指標がどれくらいばらつくかを 4 つの観点（best_score / statistical_fit / utility_proxy / privacy_proxy）で測ります。

## 仮説

- **H4a**: 同一設定 × 異なる seed でも、4 指標の **CV（変動係数 = std/mean）は 5% 以内** に収まる（改善ループは決定論的でなくとも安定）
- **H4b**: bootstrap percentile 95% CI は seed 平均から ±10% 以内に収まる（後続実験のサンプル数設計に使える）

## 仮説の評価方法

各 trial の 4 指標を `expected/trial_metrics.csv`（25 行）に固定し、

- 指標ごとに `seed_mean` / `seed_std` / `seed_cv = std / mean`
- `n_bootstrap=2000` 回の percentile 法 95% CI（`synthpop_jp.compare.stats.bootstrap_ci`、固定 RNG `np.random.default_rng(42)`）

を `expected/variance_summary.csv` にまとめます。

## 入力データ

- 元データ: `data/sample_case/`（リポジトリ同梱、100 世帯）
- improve loop の base settings は `configs/improve_quick.yaml`

## 固定パラメータ

| 項目 | 値 |
|---|---|
| seeds | `[1, 2, 3, 4, 5]` (n=5) |
| n_trials / seed | 5 |
| 戦略 | `rule_based` 固定 |
| 世帯数 | 100 |
| 目的関数 | strict_extended (Murata 式(3) 21 統計) |
| 初期生成 | zero-error init |
| 冷却 | `ExponentialCooling(T0=1.0, alpha=0.999)` |
| bootstrap | `n_bootstrap=2000`, `confidence=0.95`, RNG seed `42` |
| 評価値 CSV | `expected/trial_metrics.csv`, `expected/variance_summary.csv` |

## 想定実行時間

- CI 既定: 約 2〜3 分（25 SA runs。1 run ≈ 5 秒の見込み）

## 再現コマンド

```bash
make paper-results-exp04
make paper-results-write
```

## 出力 CSV 構造

### `expected/trial_metrics.csv`

| seed | trial_id | best_score | statistical_fit | utility_proxy | privacy_proxy |
|---:|---:|---:|---:|---:|---:|
| 1 | 1 | 453.0 | 453.0 | 0.7717 | 0.0 |
| 1 | 2 | ... | ... | ... | ... |
| ... | ... | ... | ... | ... | ... |

5 seeds × 5 trials = 25 行。

### `expected/variance_summary.csv`

| metric | seed_mean | seed_std | seed_cv | bootstrap_ci_low | bootstrap_ci_high |
|---|---:|---:|---:|---:|---:|
| best_score | 425.5 | 12.3 | 0.0289 | 401.5 | 449.5 |
| statistical_fit | ... | ... | ... | ... | ... |
| utility_proxy | ... | ... | ... | ... | ... |
| privacy_proxy | ... | ... | ... | ... | ... |

4 行。25 試行を 1 つの母集団とみなして mean / std / CV / bootstrap CI を計算する。
