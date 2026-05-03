# Changelog

This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
v0.x 中は破壊的変更を許容する。

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

研究プロトタイプとして「作る／整える／評価する」の 3 軸が揃い、`synthpop-jp` CLI 1 本で生成・評価・比較を実行できる。現状の到達点と残タスクは [`docs/status.md`](docs/status.md) を参照。

### Added — 生成 / 最適化（作る・整える）

- pydantic v2 ベースの設定ローダ（行番号付きエラー）と SeedRegistry による階層的乱数管理（同 seed で bitwise 一致の決定性）
- `PopulationArrays` + Registry + Household / Person のドメインモデル
- 9 family_type からの初期人口生成（決定論的 Largest Remainder で SA 開始時点の F-W 統計誤差を 0 に）
- family_type × role × sex 分布に応じた年齢サンプリング保証
- SA runner（Metropolis、ExponentialCooling、`trace.jsonl` + rich 進捗、checkpoint / `--resume` 対応）
- 遷移: AgeChange（§12.2A）/ AgeSwap（§12.2B）/ Hybrid（age-change と age-swap を確率混合、線形 `p_change` スケジュール対応、§12.2C）
- 目的関数: minimal（5 統計）/ extended（family_type × sex pyramid を 18 統計追加）/ strict_extended（D, E 除外、Murata 式(3) 準拠）。strict_extended は Murata 2017 Table 13 の 21 統計と完全一致（spec §11.3.2 で対応表を明記）
- `ObjectiveState` の O(1) 差分更新と再計算との整合性 hypothesis property test
- 性能ゲート達成: SA 1,000 世帯 × 20 万反復が median 5.2 秒（目標 30 秒）

### Added — 評価（3 層）

- 統計整合性: `AggregateStatL1Evaluator`（Table 13 形式の `report.md` 自動追記）/ `RareCellEvaluator`
- 有用性: `BroadUtilityEvaluator`（mixed-type 相関 / pair-TV / Frobenius 差）/ `NarrowUtilityEvaluator`（TSTR/TRTS の固定 3 タスク）
- 秘匿性: `CAP / TCAP`（属性推論リスク baseline、Harada 2024 §5.2）/ Gower 距離をベースにした `DCR / NNDR / ARD`（前計算で 1 度だけ全距離行列を構築）
- evaluator entry_points プラグイン機構
- `synthpop-jp evaluate` で上記を順次実行し `metrics.json` に書き出し

### Added — 比較 / 報告

- `synthpop-jp compare`: n=10〜30 seed × 複数 config の SA を並列実行し、Welch's t / Wilcoxon + Holm 補正、bootstrap CI 付きで比較レポートを出力
- HTML レポート基盤（plotly inline、self-contained ≤ 1MB）
- `report.md` の出典・ライセンス自動埋込（docs/DATASET.md ベース）
- mkdocs サイト v0.2 MVP（日英 index、material テーマ、CI build）
- MIA 実装の事前登録ドキュメント（`docs/spec/mia_protocol.md`、shadow seed protocol）

### Added — 開発基盤

- Python 3.12 固定、`uv sync --frozen` 1 コマンドで開発環境構築
- ruff / pyright strict / pytest / pytest-benchmark / hypothesis を CI 4 検査として整備
- `make merge-pr PR=N` で PR ready→merge→worktree 削除→develop 同期を 1 コマンド化
- `check_cadence.py` で commit cadence を物理的に強制
- 重実験の WEIGHT.md ルール（`light` / `heavy`）と `make pm` PM ダッシュボード
- Apache-2.0 LICENSE、NOTICE、CITATION.cff、CODE_OF_CONDUCT.md、CONTRIBUTING.md、docs/DATASET.md

### Changed
- (なし)

### Deprecated
- (なし)

### Removed
- (なし)

### Fixed
- `make merge-pr` が GitHub Actions ベース PR の CheckRun を SUCCESS と認識するように修正

### Security
- (なし)

---

## 過去バージョン

まだリリースされていません。初回リリース（v0.1.0 alpha）時にこのセクションへ項目を追加します。
