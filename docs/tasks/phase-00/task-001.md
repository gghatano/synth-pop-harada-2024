# task-001: spec.md 改訂（3者レビュー反映）

## 目的

`docs/reviews/action-plan.md` §2A で確定した 3 者レビュー重大指摘を `docs/spec/spec.md` に反映し、Phase 1 以降の実装が正しい仕様の上に立つようにする。

## 前提・依存

- action-plan.md §2A を単一の真実とする。
- 命名・LICENSE は task-003 で確定済（ユーザー承認済: `synthpop-jp` / Apache-2.0）を採用する。
- 原論文 `docs/papers/murata_2017.pdf` / `docs/papers/harada_2024.pdf` の式番号・Table 番号を引用する際は版を特定してから引用する。

## 成果物

`docs/spec/spec.md` の差分 PR。以下の節を更新:

- §1 背景: Harada 2024 の位置付けを追加（評価軸の由来）。
- §5.3 → §5.4 新設: 「Murata=生成側 / Harada=評価側（ARD 等）」を明文化。§5.3 は「生成・評価・改善の考え方」のまま。
- §6 環境: Python 3.11+、パッケージ名 `synthpop_jp`、PyPI 名 `synthpop-jp`、ライセンス Apache-2.0 を追記。
- §7 入出力: 入力詳細は `docs/spec/data_contract.md` に委譲する旨を明記し、本文は概要のみ残す。
- §9 アーキテクチャ: ディレクトリツリーを `synthpop_jp` に改名、`domain/protocols.py`・`registry.py`・`plugin entry_points` を追加。
- §11.4 目的関数式の書き換え:
  - 原論文準拠モード: `f(A) = Σ_s Σ_j |c_{sj}(A) - Round(r_{sj}·m_{sj}(A))|`（式(1)）、拡張は式(3) を明記。
  - 研究拡張モード: `loss_s = (1/|cells_s|) * Σ_j |observed_rate[s,j] - target_rate[s,j]|; objective = Σ_s weight_s * loss_s` を別節で記述。
  - `weight_s` は研究拡張モード限定、実験 1 (§15.1) は原論文準拠モードで実施する旨を明示。
- §11.5 ペナルティ: 「禁止制約」は目的関数ではなくハード制約として §12.2 に移動（遷移前に弾く）。
- §11.6 新設: 「目的関数最小化と秘匿性」。rare family type × age cell の k-anonymity 下限、エントロピー正則化オプションに言及。
- §12 SA: 「内部表現は NumPy 並列配列、差分更新が前提」を明記（ADR-0001 参照）。
- §13.1 統計整合性: L1 primary、TV secondary、人口ピラミッドは 1 歳刻み / 5 歳刻みの両方報告を固定。
- §13.3 秘匿性評価を 3 層に再構成:
  - (a) 類似度 proxy: DCR / NNDR / ARD（Gower 距離、proxy 注記）
  - (b) 属性推論 baseline: **Generalized CAP / TCAP（MVP 必須）**
  - (c) shadow-based MIA: TAPAS / DOMIAS（Phase 5 stretch）
  - 距離定義の具体は `docs/spec/metrics.md` に委譲。
  - 評価用実個票の出所は `docs/assumptions.md` を参照する旨を明記。
- §14.3 改善ロジック: if-then 4 本を baseline として残し、§14.4 に Pareto / random_search を MVP として追加。`improve.strategy ∈ {rule_based, pareto, random_search}` を §18 と整合させる。
- §15 実験計画: `docs/experiment_plan.md` に事前登録（仮説・指標・検定・サンプルサイズ）してから Phase 3 着手する旨を明記。seed 数は n=10〜30、Welch's t + Holm 補正、Wilcoxon signed-rank を追記。
- §16 フェーズ: Phase 0 新設、Phase 3 を 3a / 3.5 / 3b に分割、Phase 6 (v1.0 準備) を追加。
- §17 CLI: エントリポイントを `synthpop-jp` に改名、`quickstart`, `validate-config`, `--resume`, `--dry-run`, `--log-level` サブコマンド/フラグを追加。`uvx synthpop-jp quickstart` の例を追記。
- §18 設定ファイル例: `improve.strategy` の選択肢列挙、`seed` の階層 spawning 方針、pydantic モデル参照。
- §19 テスト: 決定性テスト（同 seed で bitwise 一致）と許容幅テスト（best_score ±1%）を分離記述。
- §20 成果物: `LICENSE`, `CITATION.cff`, `CHANGELOG.md`, `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `DATASET.md` を追加。

## 受け入れ基準

- 3 レビューの「重大な指摘」項目が本 spec.md に文言として反映されていること（逐条チェック）。
- 仕様と `docs/reviews/action-plan.md` §2A の差分が無いこと。
- 原論文式(1)(3) の表記が正しく引用されていること。
- `synthetic_population` という旧名の残存がゼロ（grep で確認）。

## 推定規模

M（集中 0.5〜1 日）。差分のみの編集のため行数は多いが設計判断は action-plan.md で済んでいる。

## 参照

- `docs/reviews/action-plan.md` §2A, §1.3
- `docs/reviews/review-python.md` 指摘 1, 4, 5, 7, 8, 14
- `docs/reviews/review-privacy.md` 指摘 1, 2, 3, 4, 5, 8, 9 / S2, S3
- `docs/reviews/review-oss.md` 指摘 1, 2, 3, 4, 6
