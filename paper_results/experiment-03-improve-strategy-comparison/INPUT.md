# 実験 03: 改善ループ 3 戦略の比較

## なにを確かめたいか

改善ループ（spec §14）には 3 つの戦略を実装しました。

- **rule_based**: spec §14.3 の if-then ルールで p_change / evals_per_agent / alpha を動かす
- **pareto**: spec §14.4 の non-dominated set から近傍ジッタで次を提案する
- **random_search**: 一様サンプリング（ベースライン下限）

本実験はこれら 3 戦略を **同じ base settings × 同じ seed セット × 同じ trial 数** で並べ、

- どの戦略が composite objective（3 軸平均）でベスト trial を見つけるか
- 戦略間で statistical_fit / utility_proxy / privacy_proxy のどこに差が出るか

を可視化します。Murata 2017 が論じる SA の遷移演算子比較とは別軸の、**改善ループ層** の評価です。

## 仮説

- **H3a**: rule_based は random_search より composite が小さくなる（探索の効率が高い）
- **H3b**: pareto は random_search より composite が小さくなる
- **H3c**: rule_based と pareto の composite 差は seed 全体で 5% 以内に収まる（用途で使い分け可能）

## 入力データ

- 元データ: `data/sample_case/`（リポジトリ同梱、100 世帯）
- improve loop の base settings は `configs/improve_quick.yaml`（`evals_per_agent=200`, `max_iters=50000`）

## 固定パラメータ

| 項目 | 値 |
|---|---|
| seeds | `[1, 2, 3]`（n=3） |
| n_trials / 戦略 | 5 |
| 戦略 | `rule_based`, `pareto`, `random_search` |
| 世帯数 | 100 |
| 目的関数 | strict_extended (Murata 式(3) 21 統計) |
| 初期生成 | zero-error init |
| 冷却 | `ExponentialCooling(T0=1.0, alpha=0.999)` |
| 評価値 CSV | `expected/best_scores.csv`, `expected/strategy_metrics.csv` |

## 想定実行時間

- CI 既定: 約 5〜8 分（3 seeds × 3 戦略 × 5 trials = 45 SA runs。1 run ≈ 8 秒の見込み）

## 再現コマンド

```bash
make paper-results-exp03           # 許容幅判定
make paper-results-write           # expected/*.csv を再生成（手動）
```

## 出力 CSV 構造

### `expected/best_scores.csv`

| seed | strategy | best_trial_id | best_score | composite | statistical_fit | utility_proxy | privacy_proxy |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | rule_based | 3 | 389.0 | 0.520 | 156.0 | 0.876 | 0.150 |
| 1 | pareto | 2 | ... | ... | ... | ... | ... |
| ... | ... | ... | ... | ... | ... | ... | ... |

3 seeds × 3 戦略 = 9 行。`best_trial_id` は composite が最小だった trial。

### `expected/strategy_metrics.csv`

| strategy | statistical_fit_mean | utility_proxy_mean | privacy_proxy_mean | composite_mean |
|---|---:|---:|---:|---:|
| rule_based | 156.5 | 0.870 | 0.151 | 0.522 |
| pareto | ... | ... | ... | ... |
| random_search | ... | ... | ... | ... |

3 行。各戦略の `best_*` を seed 平均したサマリ。
