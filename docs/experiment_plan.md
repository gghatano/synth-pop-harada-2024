# Experiment Plan（実験事前登録）

**ステータス: 骨子（Phase 3 着手前に完成させ、git tag でフリーズ）**

本ドキュメントは `synthpop-jp` の §15 実験群の **事前登録（pre-registration）** 文書である。仮説・指標・統計検定・サンプルサイズ・停止条件を実験開始前に確定し、事後の指標選択バイアスを避けるために用いる。

## 目的

`docs/spec/spec.md` §15 の実験 1〜4 を、着手前に「何を測るか」で凍結する。実験走行後に指標を追加・差し替えしたくなった場合は、本書を更新せず **ADR を追加** して追記管理する（Superseded フィールドで旧版を明示）。

## 凍結手順

1. Phase 3 着手前に本書を最終化する
2. `git tag experiment-plan-v1` を打つ
3. `metrics.json` に本 tag の SHA を記録する
4. 以降の変更は ADR + 新タグ (`experiment-plan-v2`) として管理

## 実験 1（§15.1）: Murata 再現の最小比較

### 仮説

- H1a: `age-change` は `evals_per_agent` が小さい領域（例: 1000）で有利
- H1b: `age-swap` は `evals_per_agent` が大きい領域（例: 16000）で有利
- 原論文モード（§11.4.1）のみで実施

### 指標

- 主指標: 原論文式(1) の総 `f(A)`
- 副指標: 21 統計別 L1 誤差（Table 13 形式）、計算時間

### 統計検定

- Wilcoxon signed-rank test（seed 対応あり）
- Effect size: Cliff's δ

### サンプルサイズ（Issue #115 で確定）

- **CI 軽量設定**（`make paper-results`）: seed n=3、`evals_per_agent ∈ {500, 2000}`、世帯数 100。〜4 分以内に終わる退行検出用設定
- **フル設定（推奨値、別 Issue 待ち）**: seed n=10、`evals_per_agent ∈ {1000, 2000, 4000, 8000, 16000}`、世帯数 1000。Murata 2017 §15.1 と整合する論文値固定用。本実装で age_swap が 1000 世帯 × 16000 evals で 1 SA 約 1 時間と実測されたため、4 実験合計が 1 日以上にのぼる。別 Issue で 1 日タイムスロット確保時に着手
- **フル設定（実施済 scale-up smoke）**: seed n=5、`evals_per_agent ∈ {1000, 2000, 4000}`、世帯数 500。`make paper-results-full` で `expected-full/*.csv` を凍結済（PR #123）

### 停止条件

- `max_iters = evals_per_agent × n_persons` の上限到達（実装上 `target_threshold=0.0` で early-stop は使わない）

### 期待値の固定先

- CI: `paper_results/experiment-01-age-change-vs-age-swap/expected/best_scores.csv` + `stat_l1.csv`
- Full（scale-up smoke、PR #123 で凍結）: 同ディレクトリの `expected-full/` 以下（n=5 / 3 evals 水準 / 500 世帯）

## 実験 2（§15.2）: hybrid 戦略

### 仮説

- H2: 初期 `age-change` 優勢 → 後半 `age-swap` 優勢の hybrid が、単独 age-change / age-swap より総合スコアで優れる

### 指標

- 主指標: 原論文式(1) の総 `f(A)` と 21 統計別 L1 の両方
- 副指標: `p_change` / `p_swap` のスケジュール依存性

### 統計検定

- Welch's t test + Holm 補正

### サンプルサイズ（Issue #115 で確定）

- **CI 軽量設定**: seed n=3、`evals_per_agent=2000` 固定、世帯数 100、戦略 = {age_change, age_swap, hybrid}（3 戦略 × 3 ペアの Welch + Holm）
- **フル設定（推奨値、別 Issue 待ち）**: seed n=10、`evals_per_agent=4000` 固定、世帯数 1000
- **フル設定（実施済 scale-up smoke）**: seed n=5、`evals_per_agent=2000`、世帯数 500（PR #123）

### Hybrid のスケジュール

- `LinearPChange(start=0.8, end=0.2)`（前半 age_change 厚め → 後半 age_swap 厚め）
- 他スケジュール（constant 0.5、定数 0.2 → 0.8 reverse）は範囲外。後続 Issue で別実験として扱う

### 期待値の固定先

- CI: `paper_results/experiment-02-hybrid-strategy/expected/best_scores.csv`
- Full（scale-up smoke、PR #123）: 同ディレクトリの `expected-full/best_scores.csv`

## 実験 3（§15.3）: 改善戦略比較（rule_based vs pareto vs random_search）

### 仮説

- H3: pareto 戦略は rule_based に対し 3 目的（統計整合性・有用性・秘匿性）の total ranking で優れる
- 副仮説 H3a: random_search は両者のベースライン下限として機能する

### 指標

- 主指標: Pareto フロント上の non-dominated solution 数
- 副指標: 3 目的それぞれの best 値、ハイパーボリューム

### 統計検定

- Welch's t test + Holm 補正

### 改善ループ設定（Issue #119 で実装、Issue #121 で paper_results 化済）

- `synthpop-jp improve --strategy {rule_based,pareto,random_search} --trials N --seed S` を 3 戦略 × seed 群で回す
- ベース config: `configs/improve_quick.yaml`（CI 軽量、`evals_per_agent=200`, `max_iters=50000`）
- 改善対象 4 軸: `transition_kind` / `alpha` / `evals_per_agent` / `p_change`（spec §14.2）
- 出力: `outputs/improve/<strategy>_seed<S>/`（`best_config.yaml` / `summary.md` / pareto 時は `pareto_front.md`）
- 比較対象: 各 run の `summary.md` と `metrics.json` 集約。`compare` コマンドで Welch's t + Holm 補正

### サンプルサイズと停止条件（Issue #121 で確定）

- **CI 軽量設定**（`make paper-results-exp03`）: seeds=[1,2,3] × n_trials=5 × 3 戦略 = 45 SA runs / 100 世帯。実測 約 45 秒
- **停止条件**: 各 trial の SA は `max_iters = evals_per_agent × n_persons` の上限到達で打ち切り（target_threshold=0、early-stop なし）
- **期待値の固定先**: `paper_results/experiment-03-improve-strategy-comparison/expected/{best_scores.csv, strategy_metrics.csv}`
- **論文値固定（フル設定 推奨値）**: 別 Issue で 1000 世帯 + n_seeds=10 + n_trials=20 へ拡張
- **scale-up smoke（実施済、PR #123）**: 500 世帯 / n_seeds=5 / n_trials=10 で `expected-full/{best_scores.csv, strategy_metrics.csv}` を凍結

## 実験 4（§15.4）: 複数候補のばらつき

### 仮説

- H4: 同一 config で生成した複数候補の評価指標ばらつきは、seed n 増加で安定化する（SD 低下）

### 指標

- 主指標: 各評価指標の seed 間 SD
- 副指標: best の安定性

### 統計検定

- 変動係数の bootstrap CI 比較

### 改善ループ設定（Issue #121 で paper_results 化済）

- 単一 strategy（`rule_based`）を seed 群で回す
- 集約は `summary.md` と各 trial の `metrics.json` を seed 横断で stack し、`synthpop_jp.compare.stats.bootstrap_ci`（n_bootstrap=2000, 95% CI, 固定 RNG seed=42）で変動係数の信頼区間を出す

### サンプルサイズと停止条件（Issue #121 で確定）

- **CI 軽量設定**（`make paper-results-exp04`）: seeds=[1..5] × n_trials=5 = 25 SA runs / 100 世帯。実測 約 27 秒
- **停止条件**: 実験 3 と同じ（max_iters 上限）
- **期待値の固定先**: `paper_results/experiment-04-multi-trial-variance/expected/{trial_metrics.csv, variance_summary.csv}`
- **scale-up smoke（実施済、PR #123）**: 500 世帯 / n_seeds=5 / n_trials=10 で `expected-full/*` を凍結
- **実測知見**: 4 指標すべて CV ≤ 0.12% で H4 の安定化仮説を強く支持。後続実験で seed n=3 でも十分という設計判断ができる

## shadow seed 群の運用

Phase 5 の shadow-based MIA 評価のため:

- shadow generator は同一公開統計入力に対し異なる seed 群（既定 n=20）で再生成
- shadow seed は main seed と独立な `SeedSequence.spawn` 枝から取得
- TAPAS / DOMIAS はこの shadow group を使う

**Phase 5 着手前に詳細確定。**

## Pre-registration 凍結手順

1. 本書の全セクションを埋める
2. 共著者レビュー後、`git tag experiment-plan-v1` を打つ
3. tag の SHA を `metrics.json` にも記録
4. 以降の変更は ADR + 新タグ

## 履歴

- 2026-04-23: v0.0.1 骨子作成（Phase 0）
