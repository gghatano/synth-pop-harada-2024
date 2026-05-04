# paper_results — Murata 2017 再現結果の固定置き場

このディレクトリは、Murata et al. (2017) の主要実験（spec §15.1 / §15.2）と、本実装独自の改善ループ評価（Issue #121）を **固定 seed × 固定設定で再現したときの数値** として、後から第三者が確認できるよう凍結保存しているフォルダです。

## 1. 何が固定されているか

| 項目 | パス |
|---|---|
| 実験 1（age-change vs age-swap）の best_score | `experiment-01-age-change-vs-age-swap/expected/best_scores.csv` |
| 実験 1 の 21 統計別 L1（副指標） | `experiment-01-age-change-vs-age-swap/expected/stat_l1.csv` |
| 実験 2（hybrid 戦略）の best_score | `experiment-02-hybrid-strategy/expected/best_scores.csv` |
| 実験 3（改善ループ 3 戦略比較）の seed × strategy ベスト trial | `experiment-03-improve-strategy-comparison/expected/best_scores.csv` |
| 実験 3 の戦略別 seed 平均 | `experiment-03-improve-strategy-comparison/expected/strategy_metrics.csv` |
| 実験 4（複数候補ばらつき）の 25 試行 4 指標 | `experiment-04-multi-trial-variance/expected/trial_metrics.csv` |
| 実験 4 の指標別 CV + bootstrap 95% CI | `experiment-04-multi-trial-variance/expected/variance_summary.csv` |
| 各実験の入力条件・seed・コミット SHA | 各ディレクトリの `INPUT.md` |
| 各実験の解釈と統計検定 | 各ディレクトリの `report.md` |

各 `expected/*.csv` は **CI 軽量設定**（実験 1: n=3 seeds × 100 世帯 × evals 2 水準 / 実験 2: 同 1 水準 / 実験 3: 3 seeds × 3 戦略 × 5 trials × 100 世帯 / 実験 4: 5 seeds × 5 trials × 100 世帯）の出力です。論文値の最終固定版は `expected-full/`（CI の 3〜5 倍規模で、4 実験すべて）に置く設計で、`make paper-results-full` を経由して生成します。

> **scale-up smoke にとどめている理由**: spec §15 凍結値（n=10 / 5 evals 水準 / 1000 世帯）で 4 実験全走させると 1 日以上を要する（age_swap が 1000 世帯 × evals=16000 で 1 SA 約 1 時間、実測）。当面は CI の 3〜5 倍規模（n=5 / 3 evals 水準 / 500 世帯 / n_trials=10）に絞ったフル設定で `expected-full/` を凍結する。論文値の完全再現は別 Issue で 1 日以上のタイムスロット確保時に着手する。

## 2. なぜ固定するか

固定値があれば、以下のことができます。

- リファクタや依存更新で **数値がずれたとき即座に気づける**（CI で検出）
- 論文の主張がこの実装でも成り立っているかを **後追いで検証できる**
- 計算機の差・乱数経路の差を `uv sync --frozen` + `SeedRegistry` で吸収し、誰がどこで走らせても **bitwise 一致** が成立することを保証する（spec §19.3）

許容幅は spec §19.4 を一次根拠とし、`best_score` 系は ±1%、`utility` 系は ±5% で `paper_results/_shared/tolerance_check.py` が判定します。

## 3. 実験 3 / 4（改善ループ層、Issue #121 で追加）

spec §15 は実験 1〜4 を定義しています。実験 1 / 2 は SA の遷移演算子・hybrid 戦略の評価でしたが、実験 3 / 4 は **改善ループ（spec §14）の戦略を比較する** 層です。

- **実験 3**: rule_based / pareto / random_search の 3 戦略を同一 seed × n_trials で並べて、composite objective でのベスト trial と戦略別平均を出す。Welch's t + Holm 補正で戦略間有意差を判定
- **実験 4**: rule_based 戦略 1 つを 5 seeds × 5 trials = 25 試行で回し、4 指標の CV と bootstrap 95% CI を測る。後続実験のサンプルサイズ設計に使う

改善ループは Issue #119 / PR #120 で実装、本 paper_results 化は Issue #121 で完了しました。

## 4. 再現手順

### 4.1 CI 既定（〜10 分）

```bash
# 1) 依存を frozen で揃える
uv sync --frozen --all-groups

# 2) 1 コマンドで実験 1 / 2 / 3 / 4 を再実行 + 許容幅判定
make paper-results

# 個別実行
make paper-results-exp01
make paper-results-exp02
make paper-results-exp03
make paper-results-exp04
```

実測時間（CI 軽量設定、ローカル WSL2）:

| 実験 | runs | 所要時間 |
|---|---:|---:|
| experiment-01 | 12 | 約 4 分 |
| experiment-02 | 9 | 約 4.5 分 |
| experiment-03 | 45 | 約 45 秒 |
| experiment-04 | 25 | 約 27 秒 |
| 合計 | 91 | 約 9.5〜10 分 |

実測時間（**scale-up smoke** フル設定、ローカル WSL2、PR #123 で計測）:

| 実験 | runs | 設定 | 所要時間 |
|---|---:|---|---:|
| experiment-01 | 30 (5 seeds × 3 evals × 2 transitions) | n=5 / 1000–4000 evals / 500 世帯 | 約 80 分 |
| experiment-02 | 15 (5 seeds × 3 transitions) | n=5 / 2000 evals / 500 世帯 | 約 30 分 |
| experiment-03 | 150 (5 seeds × 3 戦略 × 10 trials) | n=5 / n_trials=10 / 500 世帯 | 約 25 分 |
| experiment-04 | 50 (5 seeds × 10 trials) | n=5 / n_trials=10 / 500 世帯 | 約 8 分 |
| 合計 | 245 | scale-up smoke | 約 2.5 時間 |

### 4.2 期待値の更新（手動）

数値を更新したいときは `--write-expected` モードで上書きします。レビュー必須。

```bash
make paper-results-write
```

### 4.3 フル設定（重実験、ローカル / workflow_dispatch のみ）

```bash
make paper-results-full          # 既存 expected-full と一致するか判定
make paper-results-write-full    # expected-full/*.csv を再生成
```

scale-up smoke（n=5 seeds × 3 evals 水準 × 500 世帯 / n_trials=10）。実測で 4 実験合計 約 2.5 時間。論文値の完全再現は別 Issue で。

## 5. 退行（数値ずれ）が出たとき

`make paper-results` が許容幅違反で失敗すると、`tolerance_check.py` が **どの (seed, transition, evals_per_agent, stat_id) が何 % ずれたか** を Markdown 表で標準出力（CI では `$GITHUB_STEP_SUMMARY`）に出します。確認手順:

1. ずれた行の seed / transition を確認
2. `git log` で直近の依存更新やリファクタを見直す
3. 意図したずれであれば `make paper-results-write` で expected を再生成し、`report.md` の解釈を更新してコミット
4. 意図しないずれなら原因（乱数経路、初期化、目的関数の差分更新）を特定して修正

## 6. 関連ドキュメント

- spec §14: 改善ループ（実験 3 / 4 の前提）
- spec §15.1 / §15.2: 実験 1 / 2 の論文側仕様
- spec §19.3 / §19.4: 決定性と許容幅
- `docs/experiment_plan.md`: 凍結値の事前登録（4 実験すべての仮説とサンプルサイズ）
- `docs/status.md`: 現状サマリ
- Issue #115: 本ディレクトリの作成 Issue（実験 1 / 2）
- Issue #119 / PR #120: 改善ループ実体化
- Issue #121: 実験 3 / 4 の paper_results 化
