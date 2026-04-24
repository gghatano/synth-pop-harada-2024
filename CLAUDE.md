# CLAUDE.md — 本リポジトリの開発ガイド

このファイルは、Claude Code および人間の開発者が本リポジトリで作業するときに **最初に従うべき中核ルール** をまとめたものです。
各項目の詳細な根拠や運用は、末尾のリンク先ドキュメントに委譲しています。ここでは「何を守るか」だけを短く示します。

---

## 1. 本リポジトリの目的

- Murata 2017 系の **合成人口生成** と、Harada 2024 系の **評価軸（類似度・秘匿性・効用）** を Python で再実装する研究プロトタイプである
- 最終的には `synthpop-jp` パッケージとして、生成・評価・改善ループを一貫して回せる形に育てる
- コードだけでなく、**実験の計画・結果・解釈** が後から第三者（技術者でない関係者を含む）にも追えることを重視する

「動くコードができたこと」ではなく、「**誰のどんな判断に役立ったか**」を成果物の基準にします。

---

## 2. 開発は GitHub Issue 駆動で進める

- 作業単位は **Issue 1 枚**
- Issue には必ず「誰にどんな価値を提供するか」を **最初に** 書く（機能名や実装手段を主語にしない）
- 設計・実装・実験・レビュー・PR のすべての節目で Issue 本文またはコメントに記録を残す
- コードレビューの前提は「Issue を読めば、なぜこの変更が必要だったかが理解できる」こと

詳細 → [`docs/rules/issue-driven-development.md`](docs/rules/issue-driven-development.md)

---

## 3. 標準フロー（0〜4）

1 つの Issue は必ず次の 5 段階を通ります。各段階は `.claude/skills/` に対応する skill があり、Claude Code 上で `/0_issue_create` のように呼び出せます。

| # | 段階 | 目的 | 主な出力 |
|---|---|---|---|
| 0 | `0_issue_create` | 価値起点で Issue を作る | GitHub Issue 本文 |
| 1 | `1_issue_plan` | 実装前に設計・テスト・実験計画を固める | Issue コメント or `docs/plans/` への計画メモ |
| 2 | `2_issue_impl` | TDD で小さく実装する | コード + テスト + コミット列 |
| 3 | `3_review_and_refactor` | 自己レビューと整理 | Issue コメント（レビューサマリ）、必要ならリファクタ差分 |
| 4 | `4_create_pr` | `develop` 向け PR を作る | PR 本文 + レビュー依頼 |

段階を飛ばさないでください。「Issue を立てずに branch を切る」「plan を書かずに実装する」は禁止です。

---

## 4. 必須の開発プラクティス

### 4.1 TDD（テスト駆動開発）を基本にする

- 新しい振る舞いには、まず **落ちるテスト** を書いてから実装する
- Red → Green → Refactor の 3 ステップを原則として守る
- 例外として「探索的に試したい実験コード」は `experiments/` 配下に分離し、そちらには厳密な TDD を要求しない（代わりに再現性のルールを要求する）

詳細 → [`docs/rules/tdd.md`](docs/rules/tdd.md)

### 4.2 git worktree を必ず使う

- 開発はすべて worktree 上で行う。**リポジトリ直下（main / develop）で直接編集しない**
- worktree の場所は `<repo_root>/gitworktree/feature-<issue番号>-<キーワード>` に固定
- worktree 名 = ブランチ名 で揃える

詳細 → [`docs/rules/git-worktree.md`](docs/rules/git-worktree.md)

### 4.3 ブランチは `develop` 起点の `feature/...`

- 開発の基点は `develop` ブランチ。`main` は安定版のみ
- 作業ブランチ名は `feature/<issue番号>-<短いキーワード>`（例: `feature/42-add-sa-core`）

詳細 → [`docs/rules/branch-strategy.md`](docs/rules/branch-strategy.md)

### 4.4 実験は再現可能にする

- seed、データ、設定、コミット SHA を必ず記録する
- 実験ごとに Markdown レポートを `experiments/<日付>-<slug>/` に作り、**HTML 化して保存** する
- 失敗した実験も捨てずに記録する（後から仮説を振り返るため）

詳細 → [`docs/rules/experiment-management.md`](docs/rules/experiment-management.md) / [`docs/rules/html-reporting.md`](docs/rules/html-reporting.md)

### 4.5 ドキュメントは非技術者にも読める形で書く

- 1 文を長くしない。専門用語には一言の補足を添える
- 「何が変わるか」「なぜ必要か」を先に書く。実装詳細はその後
- 箇条書きだけで済ませず、短くてよいので地の文で文脈を書く

詳細 → [`docs/rules/documentation-style.md`](docs/rules/documentation-style.md)

---

## 5. Claude Code にとっての動作ルール

Claude Code がこのリポジトリで作業するときは、以下を **暗黙の前提** として振る舞ってください。

1. **計画なしに実装を始めない**。必ず `1_issue_plan` に相当する計画を Issue または `docs/plans/` に残してからコードを変更する
2. **worktree 外で編集しない**。`git status` 時点でブランチが `develop` / `main` なら、編集前に worktree を作る
3. **テストを先に書く**。実装のみのコミットを作らない（探索的な `experiments/` 配下を除く）
4. **実験結果は必ず記録する**。`experiments/<日付>-<slug>/report.md` を作り、コミットに含める
5. **Issue と PR の本文を埋める**。テンプレートの欄を空にしたまま Submit しない
6. **非技術者に説明可能か自問する**。レビュー段階で、Issue の「背景」「価値」「成功条件」を読み返し、用語が通じるか確認する

Claude Code は、これらを満たさない状態で作業を終えないこと。満たせない場合はユーザーに確認を求めてください。

---

## 6. 参照先インデックス

| 目的 | 参照先 |
|---|---|
| 最初に読む全体像 | [`docs/getting-started/development-workflow.md`](docs/getting-started/development-workflow.md) |
| Issue の書き方 | [`docs/rules/issue-driven-development.md`](docs/rules/issue-driven-development.md) |
| TDD の進め方 | [`docs/rules/tdd.md`](docs/rules/tdd.md) |
| worktree の使い方 | [`docs/rules/git-worktree.md`](docs/rules/git-worktree.md) |
| ブランチ戦略 | [`docs/rules/branch-strategy.md`](docs/rules/branch-strategy.md) |
| CI parity（push 前 4 コマンド） | [`docs/rules/ci-parity.md`](docs/rules/ci-parity.md) |
| 実験管理 | [`docs/rules/experiment-management.md`](docs/rules/experiment-management.md) |
| HTML レポート運用 | [`docs/rules/html-reporting.md`](docs/rules/html-reporting.md) |
| 文章スタイル | [`docs/rules/documentation-style.md`](docs/rules/documentation-style.md) |
| Issue テンプレート | [`.github/ISSUE_TEMPLATE/feature_value_driven.md`](.github/ISSUE_TEMPLATE/feature_value_driven.md) |
| PR テンプレート | [`.github/pull_request_template.md`](.github/pull_request_template.md) |
| 計画メモ雛形 | [`docs/templates/issue_plan.md`](docs/templates/issue_plan.md) |
| 実験レポート雛形 | [`docs/templates/experiment_report.md`](docs/templates/experiment_report.md) |
| レビューサマリ雛形 | [`docs/templates/review_summary.md`](docs/templates/review_summary.md) |
| 標準フロー skill | [`.claude/skills/`](.claude/skills/) |
| マルチエージェント運用 | [`.claude/skills/multi_agent_orchestration.md`](.claude/skills/multi_agent_orchestration.md) |
