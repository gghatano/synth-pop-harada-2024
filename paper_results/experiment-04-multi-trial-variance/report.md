# 実験 04 — 複数候補ばらつきの定量化

実施日: 2026-05-04
担当: Claude Code（Issue #121 phase-6）
コード: `paper_results/experiment-04-multi-trial-variance/run.py`

---

## 1. なにを確かめた実験か（非技術者向け）

改善ループは **同じ設定でも、種が違えば違う候補列** を出します。本実験は rule_based 戦略を 1 つに固定し、5 つの seed × 各 5 trial の合計 **25 試行** を回して、4 指標がどれくらい揺れるかを定量化します。

「揺れの大きさ」は CV（変動係数 = 標準偏差 / 平均）で表し、「平均値そのものがどこに収まりうるか」は bootstrap percentile 法 95% 信頼区間で表します。後続の paper_results 実験で「seed n=5 で十分か、増やすか」を判断する根拠データになります。

## 2. 実験条件

| 項目 | 値 |
|---|---|
| 入力データ | `data/sample_case/` (100 世帯) |
| base settings | `configs/improve_quick.yaml` (`evals_per_agent=200`, `max_iters=50000`) |
| 初期生成 | `use_zero_error_init=True` |
| 目的関数 | strict_extended (Murata 式(3) 21 統計) |
| 戦略 | `rule_based` 固定 |
| seed | `[1, 2, 3, 4, 5]` (n=5) |
| n_trials / seed | 5 |
| bootstrap | `n_bootstrap=2000`, 95% CI, RNG seed `42` |

## 3. 結果

### 3.1 全 25 試行の指標（`expected/trial_metrics.csv` 抜粋）

| seed | trial_id | best_score | statistical_fit | utility_proxy | privacy_proxy |
|---:|---:|---:|---:|---:|---:|
| 1 | 1 | 455.0 | 455.0 | 0.7751 | 0.0 |
| 1 | 2 | 454.0 | 454.0 | 0.7734 | 0.0 |
| 1 | 3〜5 | 453.0 | 453.0 | 0.7717 | 0.0 |
| 2〜3 | 全 trial | 453.0±1 | 同左 | 0.7717±0.0017 | 0.0 |
| 4 | 1 | 454.0 | 454.0 | 0.7734 | 0.0 |
| 4 | 2〜5 | 453.0 | 453.0 | 0.7717 | 0.0 |
| 5 | 1〜4 | 453.0 | 453.0 | 0.7717 | 0.0 |
| 5 | 5 | 454.0 | 454.0 | 0.7734 | 0.0 |

完全な値は `expected/trial_metrics.csv` を参照。

### 3.2 指標別の分散サマリ（`expected/variance_summary.csv`）

| metric | seed_mean | seed_std | seed_cv | bootstrap_ci_low | bootstrap_ci_high |
|---|---:|---:|---:|---:|---:|
| best_score | 453.24 | 0.5228 | 0.0012 | 453.04 | 453.48 |
| statistical_fit | 453.24 | 0.5228 | 0.0012 | 453.08 | 453.48 |
| utility_proxy | 0.7721 | 0.000891 | 0.0012 | 0.77186 | 0.77247 |
| privacy_proxy | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

### 3.3 解釈

- **CV はすべて 0.12% 以下**（H4a の 5% 上限を大きく下回る）。本 100 世帯設定では rule_based の出力が極めて安定しており、seed n=5 でも十分すぎる検出力が得られます
- **bootstrap 95% CI 幅は seed_mean からほぼ ±0.05% 以内**（H4b の 10% 上限も大きく下回る）。後続実験のサンプルサイズ設計では「`use_zero_error_init=True` を使う限り n=3 でも十分」と判断できる根拠になります
- privacy_proxy（rare cell unique 率）は 25 試行すべてで 0.0。100 世帯規模では 1 人だけ持つ属性組合せが少なく、本指標で改善ループの優劣を測るのは難しいことが分かります（後続の DCR / NNDR / ARD など Issue #99 系メトリクスへの移行が必要）
- 25 試行のうち **20 試行が best_score = 453.0** に張り付き、残り 5 試行も 454〜455 の狭い帯に収まりました。これは `use_zero_error_init=True` で初期 best_score が 453 付近の局所最適に着地し、improve loop の rule_based がそこから外れる確率が低いためです（exp03 でも観測した挙動）

> **CV / bootstrap CI の解釈に関する注意**: 本実験では n=25 の試行を 1 つの母集団とみなしており、seed 間とseed 内の分散を区別していません。改善ループの「真の trial 間ばらつき」を測るには、seed × trial の階層モデルへの移行が必要です（後続 Issue 候補）。本実験の数値は「同一設定で 25 回引いたときの 95% は seed_mean の周辺どこに着地するか」の経験的範囲として読んでください。

## 4. 既知の限界

- **n=5 / n_trials=5 / 100 世帯は CI 予算（30 分）に収めるための妥協値**。論文値の最終固定としては不十分。フル設定（後続 Issue で拡張）で seed n=10 / 1000 世帯を再走査する想定
- privacy_proxy 列が 0 で固定されるため、CV / CI の数値が縮退する。秘匿性のばらつきを測るには分布の裾を評価する別指標が必要（DCR / NNDR / ARD は Issue #99 で導入済）
- bootstrap RNG seed を 42 固定にしているため、`expected/variance_summary.csv` は決定論的に再生成できるが、本実験以外の paper_results CI と独立した RNG 路を持つことになる（spec §19.3 の「RNG 経路は SeedRegistry 1 本に統一」とは別系統）

## 5. 再現コマンド

```bash
make paper-results-exp04            # CI 既定で許容幅判定
make paper-results-write            # expected/*.csv 再生成（手動更新）
```

実測時間（n=5 / 100 世帯 / n_trials=5、ローカル WSL2）:

| 実験 | runs | 所要時間 |
|---|---:|---:|
| experiment-04 | 25 (5 seeds × 5 trials) | 約 27 秒 |
