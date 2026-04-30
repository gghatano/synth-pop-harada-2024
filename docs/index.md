# synthpop-jp ドキュメント

Murata 2017 系の **合成人口生成** と Harada 2024 系の **評価軸** を Python で再実装する研究プロトタイプの公式ドキュメントです。

## 何ができるか

- 公開されている **国勢調査の集計表のみ** から、内部整合性のとれた合成世帯・人口マイクロデータを生成
- 統計整合性 / 有用性 / 秘匿性の 3 層で評価レポートを自動生成
- 生成パラメータの改善ループ（rule_based / Pareto）で「使える」合成人口を探索（Phase 5 予定）

## 最初に読む順番

1. **[開始ガイド](getting-started/development-workflow.md)**: 開発フロー全体
2. **[手法と使い方](guides/how-it-works.md)**: SA / 遷移 / 目的関数 / 評価器の解説
3. **[進捗オーバービュー](reports/2026-04-30-progress-overview.md)**: 現状の到達点

## 開発に参加する

[`rules/`](rules/issue-driven-development.md) 配下で Issue 駆動・TDD・git worktree などのルールを参照してください。

## 仕様と評価

- [仕様 (spec)](spec/spec.md) — 全体仕様
- [評価指標](spec/metrics.md) — broad / narrow utility / privacy 3 層
- [MIA Protocol](spec/mia_protocol.md) — Phase 5 実装の事前登録
- [実験レポート形式](spec/experiment_report_format.md) — 実験記録のスキーマ

## English

[Home (EN)](index.en.md) を参照してください。
