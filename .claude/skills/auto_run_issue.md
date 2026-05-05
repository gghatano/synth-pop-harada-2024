---
name: auto_run_issue
description: 1 コマンドで Issue 起票 → plan → 実装 → independent review → PR → merge → worktree 片付けまで自律走破する。各段階の出力は Issue コメントとして記録される。
---

# SKILL: auto_run_issue — Issue を 0→5 まで自律走破する

## 目的

Claude Code の **親セッションが 1 コマンドで Issue 起票から merge / 片付けまでを自律走破** できるようにする薄いオーケストレータ。
途中で人間のレビューを挟まなくても、各節目の記録が **Issue コメント** として残るので、後から事後レビューが可能。

各段階の institutional knowledge は既存 skill (`0_issue_create.md` 〜 `5_merge_and_cleanup.md`) に温存されており、
本 skill は **既存 skill を Read で読み込んで地の文として従う** 方式で薄く保つ。
Skill tool の再帰起動は採用しない（親セッション 1 階層のみ）。

## 使う場面

- ユーザーがタイトル文字列 or 既存 Issue 番号を渡して「自律走破して」と言ったとき
- バックログから次の Issue を 1 本ずつ片付けるとき（タイトル指定 → 起票 → merge まで）
- 既存 Issue の段階 1〜5 だけを走らせるとき（Issue 番号指定で 0 をスキップ）

## 入力

- **タイトル文字列** （新規 Issue を起票する場合） もしくは
- **既存 Issue 番号** （起票済の場合は段階 1 から開始）
- 任意: 依存 PR 一覧、想定規模、用途別ロール（implementer / documentation engineer など）

## フロー

各ステップで「親セッションの責務」と「sub-agent 委譲時のプロンプト雛形参照先」を明記する。

### 0. Issue 起票

- 親が [`0_issue_create.md`](0_issue_create.md) を Read して従う
- ユーザーがタイトルだけを渡した場合は、価値起点で本文を組み立てて `gh issue create --title ... --body ...` で起票
- 既存 Issue 番号が渡された場合は本ステップをスキップ
- 完了確認: `gh issue view <N> --json body` で本文非空

### 1. worktree 作成

- 親直実行（[`docs/rules/git-worktree.md`](../../docs/rules/git-worktree.md)）
- コマンド例:
  ```bash
  cd <repo_root>
  git fetch origin
  git worktree add -b feature/<N>-<keyword> gitworktree/feature-<N>-<keyword> origin/develop
  cd gitworktree/feature-<N>-<keyword>
  uv sync --frozen
  uv run pytest -q   # baseline 確認
  ```
- 完了確認: `git worktree list` に `feature-<N>-*` あり

### 2. plan 作成

- 親 or sub-agent が [`1_issue_plan.md`](1_issue_plan.md) を Read
- Issue コメントとして `## 実装計画` を投稿（`gh issue comment <N> --body ...`）
- 詳細は [`docs/templates/issue_plan.md`](../../docs/templates/issue_plan.md) を参照
- 完了確認: `gh issue view <N> --comments` に `## 実装計画` 見出しあり

### 3. impl 実行

- sub-agent (general-purpose) に委譲
- プロンプトは [`subagent_prompt_template.md`](subagent_prompt_template.md) の **implementer 用雛形** を使う
- sub-agent には [`2_issue_impl.md`](2_issue_impl.md) を Read させ、TDD（Red → Green → Refactor、test と feat は別 commit）で実装させる
- 依存 PR の merged commit hash と使える API を A〜E の必須要素として明示する
- 完了確認: `git log feature/<N>-* --oneline` に `test:` と `feat:` の交互コミット、`uv run pytest` 緑

### 4. independent review

- 別 sub-agent（実装者と独立した一般エージェント）に diff + Issue + plan を渡してレビューだけさせる
- プロンプトは [`subagent_prompt_template.md`](subagent_prompt_template.md) の **reviewer 用雛形** を使う
- reviewer agent は [`3_review_and_refactor.md`](3_review_and_refactor.md) を Read し、`git diff develop..HEAD` を入力に **Issue コメントへ `## レビューサマリ` を投稿** する。本体コードは触らない
- 完了確認: `gh issue view <N> --comments` に `## レビューサマリ` あり

### 5. PR 作成 → CI 緑待ち → merge → worktree 片付け

- 親が [`4_create_pr.md`](4_create_pr.md) と [`5_merge_and_cleanup.md`](5_merge_and_cleanup.md) を Read して従う
- 段階 4 (PR 作成 → Draft → Ready) と段階 5 (merge → 片付け) の責任分界点に注意
- merge は `make merge-pr PR=<N>` 1 コマンド（`scripts/merge_pr.py` 経由）
- 完了確認: `gh pr view <N> --json state` が `MERGED`、`git worktree list` に該当 worktree が無い

## DoD 検証コマンド表

各段階の完了確認は以下のコマンド 1 本で行える。親セッションは段階を跨ぐ前に該当行を実行して green を確認する。

| 段階 | 完了確認コマンド |
|---|---|
| 0 | `gh issue view <N> --json body` で本文非空 |
| 1 | `git worktree list` に `feature-<N>-*` あり |
| 2 | `gh issue view <N> --comments` に `## 実装計画` 見出しあり |
| 3 | `git log feature/<N>-* --oneline` に `test:` と `feat:` の交互コミット、`uv run pytest` 緑 |
| 4 | `gh issue view <N> --comments` に `## レビューサマリ` あり |
| 5 | `gh pr view <N> --json state` が `MERGED`、worktree 不在 |

## 失敗時の自律復旧表

各段階で失敗が発生したときの自律復旧フローと「諦めライン」（超えたら user にエスカレーション）を以下に固定する。

| 失敗 | 自律対応 | 諦めライン |
|---|---|---|
| CI 落ち（lint / format） | sub-agent に修正タスク再委譲（diff + 失敗ログ付き） | 2 回 |
| pyright / pytest 落ち | sub-agent に修正タスク（diff + 失敗ログ付き） | 2 回 |
| Independent review が Critical 指摘 | 修正タスク再委譲 | 1 回 |
| conflict | 親が `git rebase origin/develop` で解決、解決不能なら user に報告 | 1 回 |
| sub-agent self-stall（10 分無音） | 中間 commit + WIP draft PR + 親が引き継ぐ | 即時 |

**諦めラインを超えたら user にエスカレーション** する。沈黙して諦めない。

## 完了条件（auto_run_issue 自体の DoD）

- [ ] PR が `MERGED` になっている（`gh pr view <N> --json state`）
- [ ] worktree が削除済み（`git worktree list` に該当行なし）
- [ ] Issue が `closed` になっている（`Closes #<N>` で auto-close されているか、明示的に `gh issue close <N>` を叩いた）
- [ ] ユーザーへの完了報告: PR URL / 追加テスト数 / 所要時間 / 主要な論点

## 注意点

- **既存 skill を Read で読み込む方式を崩さない**。本 skill にロジックを書き溜めない（薄く保つ）
- **sub-agent に Agent を再帰起動させない**。階層が深くなると管理不能になる
- **諦めラインを超えたら必ず user にエスカレーション**。沈黙して諦めない
- **Issue コメントを正史にする**。各段階の出力は必ず Issue コメントに残す。Slack や口頭で済ませない
- **plan を書かずに impl に進まない**。段階 2 をスキップすると後段の独立レビューが空回りする
- **重実験 worktree ルールを守る**（[`pm_sop.md`](pm_sop.md) §「重実験 worktree」参照）。`heavy` 宣言された worktree が active な間は新規 Agent を起動しない

## 関連 skill

- 親セッションの行動規範: [`pm_sop.md`](pm_sop.md)
- sub-agent プロンプト雛形: [`subagent_prompt_template.md`](subagent_prompt_template.md)
- 段階別 skill: [`0_issue_create.md`](0_issue_create.md), [`1_issue_plan.md`](1_issue_plan.md), [`2_issue_impl.md`](2_issue_impl.md), [`3_review_and_refactor.md`](3_review_and_refactor.md), [`4_create_pr.md`](4_create_pr.md), [`5_merge_and_cleanup.md`](5_merge_and_cleanup.md)
