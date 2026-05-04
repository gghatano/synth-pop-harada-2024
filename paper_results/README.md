# paper_results — Murata 2017 再現結果の固定置き場

このディレクトリは、Murata et al. (2017) の主要実験（spec §15.1 / §15.2）を **本実装で固定 seed × 固定設定で再現したときの数値** を、後から第三者が確認できるよう凍結保存しているフォルダです。

## 1. 何が固定されているか

| 項目 | パス |
|---|---|
| 実験 1（age-change vs age-swap）の best_score | `experiment-01-age-change-vs-age-swap/expected/best_scores.csv` |
| 実験 1 の 21 統計別 L1（副指標） | `experiment-01-age-change-vs-age-swap/expected/stat_l1.csv` |
| 実験 2（hybrid 戦略）の best_score | `experiment-02-hybrid-strategy/expected/best_scores.csv` |
| 実験 1 / 2 の入力条件・seed・コミット SHA | 各ディレクトリの `INPUT.md` |
| 実験 1 / 2 の解釈と統計検定 | 各ディレクトリの `report.md` |

各 `expected/*.csv` は **CI 軽量設定**（n=3 seeds × 100 世帯 × evals_per_agent 2 水準。実験 2 は単一水準）の出力です。論文値の最終固定版は `expected-full/`（n=10 / 5 水準 / 1000 世帯）に置く設計ですが、本 Issue では空のままで、`make paper-results-full` を `workflow_dispatch` 経由で走らせて生成する想定です。

## 2. なぜ固定するか

固定値があれば、以下のことができます。

- リファクタや依存更新で **数値がずれたとき即座に気づける**（CI で検出）
- 論文の主張がこの実装でも成り立っているかを **後追いで検証できる**
- 計算機の差・乱数経路の差を `uv sync --frozen` + `SeedRegistry` で吸収し、誰がどこで走らせても **bitwise 一致** が成立することを保証する（spec §19.3）

許容幅は spec §19.4 を一次根拠とし、`best_score` 系は ±1%、`utility` 系は ±5% で `paper_results/_shared/tolerance_check.py` が判定します。

## 3. なぜ実験 3 / 4 が無いか

spec §15 は実験 1〜4 を定義していますが、本 Issue（#115）では 1 / 2 のみを扱います。理由は単純で、**実験 3（rule_based vs pareto）と実験 4（複数候補ばらつき）は改善ループ（spec §14）の実装が前提** で、改善ループはまだ未実装だからです。改善ループ実装後の後続 Issue で `paper_results/experiment-03-...` / `experiment-04-...` を追加する想定です。

## 4. 再現手順

### 4.1 CI 既定（〜10 分）

```bash
# 1) 依存を frozen で揃える
uv sync --frozen --all-groups

# 2) 1 コマンドで実験 1 / 2 を再実行 + 許容幅判定
make paper-results
```

実測時間（n=3 / 100 世帯）:

| 実験 | runs | 所要時間 |
|---|---:|---:|
| experiment-01 | 12 | 約 4 分 |
| experiment-02 | 9 | 約 4.5 分 |
| 合計 | 21 | 約 8.5 分 |

### 4.2 期待値の更新（手動）

数値を更新したいときは `--write-expected` モードで上書きします。レビュー必須。

```bash
make paper-results-write
```

### 4.3 フル設定（重実験、ローカル / workflow_dispatch のみ）

```bash
make paper-results-full
```

n=10 seeds × 5 evals 水準 × 1000 世帯。通常 1〜2 時間かかるため CI では走らせません。GitHub Actions の `paper-results` workflow を `workflow_dispatch` で `full=true` にすると CI 上でも実行できます。

## 5. 退行（数値ずれ）が出たとき

`make paper-results` が許容幅違反で失敗すると、`tolerance_check.py` が **どの (seed, transition, evals_per_agent, stat_id) が何 % ずれたか** を Markdown 表で標準出力（CI では `$GITHUB_STEP_SUMMARY`）に出します。確認手順:

1. ずれた行の seed / transition を確認
2. `git log` で直近の依存更新やリファクタを見直す
3. 意図したずれであれば `make paper-results-write` で expected を再生成し、`report.md` の解釈を更新してコミット
4. 意図しないずれなら原因（乱数経路、初期化、目的関数の差分更新）を特定して修正

## 6. 関連ドキュメント

- spec §15.1 / §15.2: 実験 1 / 2 の論文側仕様
- spec §19.3 / §19.4: 決定性と許容幅
- `docs/experiment_plan.md`: 凍結値の事前登録
- `docs/status.md`: 現状サマリ
- Issue #115: 本ディレクトリの作成 Issue
