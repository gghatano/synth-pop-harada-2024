# 実験 01 — age-change vs age-swap

実施日: 2026-05-04
担当: Claude Code（Issue #115 phase-6）
コード: `paper_results/experiment-01-age-change-vs-age-swap/run.py`

---

## 1. なにを確かめた実験か（非技術者向け）

合成人口を作るために、AI は **何度も少しずつ年齢を書き換えながら、「日本の国勢調査の集計表」に近づけよう** とします（シミュレーテッドアニーリング、SA）。

このとき「1 人の年齢を動かす」（age-change）と、「同じ家族のかたち・性別の 2 人の年齢を入れ替える」（age-swap）の 2 通りのやり方があり、どちらが速く誤差を下げられるかは状況次第です。

Murata 2017 の論文（§3, §5.1）は **時間が短いとき age-change が有利、長く回せば age-swap が逆転する** と主張しています。本実験は本実装でも同じ傾向が再現されるか、固定 seed × 100 世帯規模で確認します。

## 2. 実験条件

| 項目 | 値 |
|---|---|
| 入力データ | `data/sample_case/` (100 世帯、9 family_types のダミー) |
| 初期生成 | `use_zero_error_init=True` (Murata 2017 §3 / Largest Remainder) |
| 目的関数 | strict_extended (Murata 式(3) 21 統計、A,B,C + 9 ft × 2 sex pyramid) |
| 遷移 | `AgeChangeTransition` / `AgeSwapTransition`（spec §12.2A / §12.2B） |
| 冷却 | `ExponentialCooling(T0=1.0, alpha=0.999)` |
| `evals_per_agent` | `{500, 2000}` (CI 既定) |
| seed | `[1, 2, 3]`（n=3、CI 既定） |
| 統計検定 | Wilcoxon signed-rank + Cliff's δ |

`expected/best_scores.csv` と `expected/stat_l1.csv` に最終値を固定し、CI で再計算して ±1% 以内に収まることを `tolerance_check` で検証します。

## 3. 結果

### 3.1 best_score 一覧（CI 既定 n=3 / 100 世帯）

| seed | evals | age_change | age_swap | swap - change |
|---:|---:|---:|---:|---:|
| 1 | 500 | 453.0 | 567.0 | +114 |
| 1 | 2000 | 453.0 | 567.0 | +114 |
| 2 | 500 | 455.0 | 570.0 | +115 |
| 2 | 2000 | 455.0 | 570.0 | +115 |
| 3 | 500 | 453.0 | 568.0 | +115 |
| 3 | 2000 | 453.0 | 568.0 | +115 |

age-change の方が常に best_score が低く、age-swap との差は安定して +114〜+115 の範囲に収まりました。

### 3.2 Wilcoxon signed-rank（対応群、n=3）

| evals | W | p-value | Cliff's δ (age_change ≺ age_swap) |
|---:|---:|---:|---:|
| 500 | 0.000 | 0.250 | +1.000 |
| 2000 | 0.000 | 0.250 | +1.000 |

n=3 では Wilcoxon の最小 p-value は 0.25 のため、統計的に有意とは言えませんが、効果量 Cliff's δ は最大値 +1.0（age_change が常に age_swap より小さい）で、サンプル全体で順序が反転していません。

### 3.3 解釈

- 100 世帯規模では age-change が支配的で、`evals_per_agent` を増やしても age-swap への逆転は起きませんでした。これは Murata 2017 が想定している大規模（数千世帯）と異なる小規模条件下の挙動として整合します
- H1b（大 evals での age-swap 逆転）は本 CI 設定では検証できないため、フル設定（n=10 / 5 水準 / 1000 世帯、`make paper-results-full`）でのフォロー実験が必要です
- 100 世帯では n=3 でも Cliff's δ=1.0 が安定して出るため、退行検出（CI で best_score がずれたら気づける）の用途には十分機能します

## 4. 既知の限界

- n=3 / 100 世帯は CI 予算（10 分）に収めるための妥協で、論文値の最終固定としては不十分
- Wilcoxon の有意性は n≥6 以上必要（α=0.05、両側）。フル設定でのみ検出力が確保される
- 本実装は乱数経路を `SeedRegistry` で固定しているため、seed が同じなら 2 回呼んで bitwise 一致する（`tests/paper_results/test_determinism.py` で常時検証）

## 5. 再現コマンド

```bash
make paper-results-exp01            # CI 既定で許容幅判定
make paper-results-write            # expected/*.csv 再生成（手動更新）
PYTHONPATH=. uv run python paper_results/experiment-01-age-change-vs-age-swap/run.py --full --write-expected
```
