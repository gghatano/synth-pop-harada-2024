# 実験 02: hybrid 戦略 (Murata 2017 §15.2)

## なにを確かめたいか

実験 01 で扱った age-change と age-swap を **確率的に混合する** HybridTransition
（spec §12.2C）が、単独の age-change / age-swap より総合的に優れているかを
確認します。

- **H2**: 初期 age-change 優勢 → 後半 age-swap 優勢の hybrid（線形 p_change スケジュール）が、単独 age-change / age-swap より best_score が低くなる

## 仮説の評価方法

各 `seed` で 3 戦略すべてを SA で 1 回ずつ回し、`best_score` を比較します。
3 ペア（change vs swap、change vs hybrid、swap vs hybrid）について Welch's t
test を行い、p 値群に Holm-Bonferroni 補正を適用します（既存
`src/synthpop_jp/compare/stats.py` を流用）。

## 入力データ

- 元データ: `data/sample_case/`（実験 01 と同じ）
- 100 世帯ベースを `paper_results._shared.runner._scale_sample_case` で整数倍
  スケール

## 固定パラメータ

| 項目 | CI 既定 | フル設定 (`--full`) |
|---|---|---|
| seeds | `[1, 2, 3]`（n=3） | `[1..10]`（n=10） |
| `evals_per_agent` | `2000`（固定） | `4000`（固定） |
| 世帯数 | 100 | 1000 |
| 戦略 | `age_change`, `age_swap`, `hybrid` | 同左 |
| 目的関数 | strict_extended (Murata 式(3) 21 統計) | 同左 |
| HybridTransition の p_change | 線形 0.8 → 0.2（`LinearPChange`） | 同左 |
| 冷却 | `ExponentialCooling(T0=1.0, alpha=0.999)` | 同左 |
| 評価値 CSV | `expected/best_scores.csv` | `expected-full/best_scores.csv` |

## 想定実行時間

- CI 既定: 約 4.5 分（9 runs）
- フル設定: 約 1 時間（30 runs、`workflow_dispatch` 限定）

## 再現コマンド

```bash
make paper-results-exp02
make paper-results-write
PYTHONPATH=. uv run python paper_results/experiment-02-hybrid-strategy/run.py --full --write-expected
```

## 再現性の指紋（spec §19.3）

- seed: `[1, 2, 3]`（CI 既定）
- commit_sha: `c045606e50f4999adb6a0b86f39b84bdd4acffc6`
- uv_lock_sha256: `dda09efe4af1e31e4f985b2b8b513267f79cfc94dce3856e678347d8def8fa82`

## 期待される結果（実測）

CI 既定（n=3 / 100 hh / evals=2000）の実測値:

| seed | age_change | age_swap | hybrid |
|---:|---:|---:|---:|
| 1 | 453.0 | 567.0 | 453.0 |
| 2 | 455.0 | 570.0 | 455.0 |
| 3 | 453.0 | 568.0 | 453.0 |

100 世帯規模の最終局面では age-change と hybrid が同じ値に収束し、age-swap
だけ一段高い値（≈ +115）に留まります。これは hybrid が後半（p_change=0.2）で
swap を 8 割選ぶ設計のため、終端の局所最適から swap で抜け出せず、age-change
段階で到達した最適に張り付くと解釈できます。
