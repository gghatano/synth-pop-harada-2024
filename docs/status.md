# 現状サマリ — synthpop-jp

このドキュメントは「いま何が動いて、何が動いていないか」を 1 枚に集約したものです。新しい貢献者やしばらく離れていた開発者が **次の作業を選ぶための入口** として使ってください。

- 最終更新: 2026-05-04
- 対象 develop SHA: `ee2e5d4`
- 本体テスト: 560 passed / 10 skipped
- Open Issue: 2 件（#47 / #103）/ Closed Issue: 55 件

---

## 1. 何ができるか（現在の機能）

### CLI サブコマンド

| サブコマンド | 役割 |
|---|---|
| `synthpop-jp quickstart` | 同梱ダミーデータから合成世帯・個人を 10 秒以内に生成 |
| `synthpop-jp generate --config foo.yaml` | 任意の設定で合成人口を生成（SA 含む） |
| `synthpop-jp validate-config configs/base.yaml` | 設定 YAML の妥当性チェック |
| `synthpop-jp evaluate <persons.csv>` | 統計誤差 / rare cell / CAP/TCAP / DCR/NNDR/ARD / broad / narrow utility を `metrics.json` に書き出し |
| `synthpop-jp compare <config>... --seeds N` | 複数 config × n seed で SA を回し、Welch / Wilcoxon + Holm 補正 + bootstrap CI 付き比較レポートを出力 |

使い方の詳細は [`docs/guides/how-it-works.md`](guides/how-it-works.md) を参照。

### 実装済みの 3 軸

合成データ品質を支える「作る／整える／評価する」の 3 軸が、Protocol で分離された独立モジュールとして揃っています。

**作る軸（遷移）** — `src/synthpop_jp/optimize/transitions.py`

- AgeChange（1 人の年齢を動かす、§12.2A）
- AgeSwap（同じ家族類型・性別の 2 人の年齢を交換、§12.2B）
- Hybrid（age-change と age-swap を確率混合、§12.2C）
- 動的 `p_change` スケジュール（線形）

**整える軸（目的関数）** — `src/synthpop_jp/optimize/objective.py`, `state.py`

- minimal（5 統計、O(1) 差分更新）
- extended（family_type × sex pyramid を 18 統計追加）
- strict_extended（D, E 統計を除外、Murata 式(3) 準拠）→ Murata 2017 Table 13 の 21 統計と完全一致（spec §11.3.2）

**評価する軸** — `src/synthpop_jp/evaluate/`, `src/synthpop_jp/domain/distance.py`

| 層 | モジュール | 内容 |
|---|---|---|
| 統計整合性 | `aggregate_metrics.py` | 統計別 L1 誤差（Table 13 形式 report.md 自動追記） |
| 統計整合性 | `rare_cell_metrics.py` | rare cell 監視 |
| 有用性 | `utility_metrics.py` | broad utility（mixed-type 相関 / pair-TV / Frobenius） |
| 有用性 | `downstream_tasks.py` | narrow utility（TSTR / TRTS の固定 3 タスク） |
| 秘匿性 | `attribute_inference.py` | CAP / TCAP（属性推論リスク baseline） |
| 秘匿性 | `privacy_metrics.py` | DCR / NNDR / ARD（Gower 距離ベース、`domain/distance.py` で 1 度だけ前計算） |

評価器は `evaluate/plugin.py` で entry_points プラグインに対応しており、外部パッケージから差し込めます。

### 性能と品質ゲート

| 項目 | 実測 | 目標 |
|---|---|---|
| `ObjectiveState.propose_change` | 1.5 μs | < 100 μs |
| `AgeChangeTransition.propose` | 7.5 μs | < 10 μs |
| SA 1,000 世帯 × 20 万反復 | 5.2 s | < 30 s |
| SA peak RSS（100k 世帯 × 200k 反復） | 358 MB | （参考） |
| 本体テスト | 560 passed / 10 skipped | — |

ベンチ詳細: [`docs/reports/phase-02-benchmarks.md`](reports/phase-02-benchmarks.md)
メモリ実測詳細: [`experiments/2026-04-29-sa-memory-profile/report.md`](../experiments/2026-04-29-sa-memory-profile/report.md)

### ドキュメント基盤

- `mkdocs.yml` v0.2 MVP（日英 index、material テーマ、CI build）
- `report.md` への出典・ライセンス自動埋め込み（DATASET.md ベース）
- MIA 実装の事前登録ドキュメント（`docs/spec/mia_protocol.md`、shadow seed protocol）

### 論文結果の固定再現（Issue #115 / #121）

- `paper_results/experiment-01-age-change-vs-age-swap/` / `experiment-02-hybrid-strategy/` に Murata 2017 §15.1 / §15.2 の **CI 軽量設定**（n=3 / 100 世帯）の `expected/*.csv` を凍結
- `paper_results/experiment-03-improve-strategy-comparison/` で改善ループ（spec §14）の rule_based / pareto / random_search 3 戦略比較が CI で常時走る（3 seeds × 3 戦略 × 5 trials, 約 45 秒）
- `paper_results/experiment-04-multi-trial-variance/` で同設定 5 seeds × 5 trials のばらつきを CV + bootstrap 95% CI で測定済（4 指標すべて CV ≤ 0.12%）
- `make paper-results` で 1 コマンド再現（4 実験合計で約 9〜10 分）+ ±1% 許容幅判定
- `make paper-results-full` で 4 実験すべての **scale-up smoke**（n=5 / 3 evals 水準 / 500 世帯 / n_trials=10）を再現可能。`expected-full/` 凍結済（feature/paper-results-full-run）。論文値の完全再現（n=10 / 5 水準 / 1000 世帯）は age_swap が 1000 hh × 16000 evals で 1 SA 約 1 時間と判明したため別 Issue で 1 日タイムスロット確保時に実施
- `.github/workflows/paper-results.yml` で PR / nightly に CI 実行
- `make audit-experiments` で `experiments/` の再現性指紋（seed / SHA / uv.lock）を機械チェック

---

## 2. できていないこと（TODO / Backlog）

### 短期 — Open Issue

| Issue | 内容 | 状態 |
|---|---|---|
| [#103](https://github.com/gghatano/synth-pop-harada-2024/issues/103) | e-Stat 実データ取り込み配管（`scripts/fetch_estat.py`） | Open（次の主要ターゲット） |
| [#47](https://github.com/gghatano/synth-pop-harada-2024/issues/47) | Agent が `make ci` 1 コマンドで CI parity 全 4 検査を確実に走らせ自己報告できる | Open（PR #89 が紐づく） |

### 中期 — 構想中（未 Issue 化）

- **改善ループ**: `improve/strategy.py` に rule_based / Pareto / random_search の骨格はあるが、multi-trial runner と best config 選択を実体化する必要あり
- **MIA 実装**: 事前登録（`docs/spec/mia_protocol.md`）まで完了。TAPAS / DOMIAS の実装は shadow dataset 取得後に着手
- **mkdocs サイトの GitHub Pages 公開**: build CI までは整備済み。デプロイ設定と既存 docs の repo-relative link を mkdocs 形式に直す作業が残る
- **Murata 2017 実験 3 / 4 のフル設定**: feature/paper-results-full-run（PR #123）で scale-up smoke（500 世帯 / n=5 / n_trials=10）の `expected-full/*.csv` を凍結済。論文値完全再現（1000 世帯 / n=10 / n_trials=20）は別 Issue
- **`paper_results/expected-full/` の論文値完全再現**: 上記別 Issue で 1 日タイムスロット確保時に実施（age_swap が 1000 世帯 × evals=16000 で 1 SA 約 1 時間という実測由来）
- **Zenodo DOI 連携と CITATION.cff の DOI 記入**

---

## 3. プロジェクト構成（コード）

```
src/synthpop_jp/
├── cli.py / config.py / registry.py / rng.py
├── domain/         # Protocol、距離、ドメインモデル
├── io/             # pydantic ローダ、writer、再構築
├── init/           # 初期人口生成（決定論的 Largest Remainder）
├── optimize/       # SA runner、遷移、目的関数、checkpoint、trace
├── evaluate/       # 評価器（aggregate / rare / utility / privacy / CAP）
├── compare/        # 統計検定 + bootstrap CI 付き比較 runner
├── improve/        # 改善戦略（rule_based / Pareto skeleton）
├── reports/        # markdown / HTML / plot 生成
└── experiments/    # 実験コード補助
```

---

## 4. 開発フロー

すべての作業は **GitHub Issue 1 枚 → worktree 作成 → TDD → PR → develop マージ** のサイクルで進めます。詳細は [`CLAUDE.md`](../CLAUDE.md) と [`docs/getting-started/development-workflow.md`](getting-started/development-workflow.md) を参照。

主要ルール:

- ブランチは `develop` 起点の `feature/<issue番号>-<キーワード>`
- worktree は `<repo_root>/gitworktree/feature-<issue番号>-<キーワード>` 固定
- 実装には常に **落ちるテストから**（`experiments/` 配下を除く）
- 実験は seed / config / SHA を必ず記録し `experiments/<日付>-<slug>/report.md` に残す

---

## 5. 関連ドキュメント

### このプロジェクトを理解したい人向け

| 目的 | 参照先 |
|---|---|
| 何ができるか / インストール | [`README.md`](../README.md) |
| 手法と CLI の使い方 | [`docs/guides/how-it-works.md`](guides/how-it-works.md) |
| 仕様 | [`docs/spec/spec.md`](spec/spec.md) |
| 評価指標の定義 | [`docs/spec/metrics.md`](spec/metrics.md) |
| MIA 実装の事前登録 | [`docs/spec/mia_protocol.md`](spec/mia_protocol.md) |

### 開発に参加する人向け

| 目的 | 参照先 |
|---|---|
| 開発フロー全体像 | [`docs/getting-started/development-workflow.md`](getting-started/development-workflow.md) |
| Issue 駆動 | [`docs/rules/issue-driven-development.md`](rules/issue-driven-development.md) |
| TDD | [`docs/rules/tdd.md`](rules/tdd.md) |
| worktree 配置 | [`docs/rules/git-worktree.md`](rules/git-worktree.md) |
| 実験管理 | [`docs/rules/experiment-management.md`](rules/experiment-management.md) |
| 文章スタイル | [`docs/rules/documentation-style.md`](rules/documentation-style.md) |

### 過去の意思決定・経緯

| 目的 | 参照先 |
|---|---|
| 3 視点レビュー統合プラン（v0.x の設計判断の背景） | [`docs/reviews/action-plan.md`](reviews/action-plan.md) |
| 主要 ADR | [`docs/adr/`](adr/) |
| Phase 2 性能ベンチ | [`docs/reports/phase-02-benchmarks.md`](reports/phase-02-benchmarks.md) |

---

## 6. このドキュメントの更新規則

- 状況が変わったら **このファイルを書き換える**（snapshot として日付別に新規作成しない）
- 機能や Open Issue が増減したら §1 / §2 を反映
- 性能ゲートが変わったら §1 末尾の表を更新
- 過去の到達点を時系列で追いたい場合は GitHub の closed PR / Issue を参照
