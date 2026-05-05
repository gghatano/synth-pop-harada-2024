---
name: 5_merge_and_cleanup
description: Ready 化された PR を merge し、worktree とローカルブランチを片付け、Issue を close する。`make merge-pr PR=<N>` を使う。
---

# SKILL: 5_merge_and_cleanup — merge と片付け

## 目的

`4_create_pr.md` から **merge 手順を分離** した専任 skill。
PR が Ready / CI 緑 / レビュー済みの状態から、`make merge-pr PR=<N>` 1 コマンドで squash merge → worktree 片付け → Issue close まで完結させる。

`make merge-pr` は `scripts/merge_pr.py` を呼ぶ thin wrapper であり、PR 状態確認・Ready 切替・squash merge・worktree remove・branch -D・develop 最新化までを 1 ストロークで処理する。
**`gh pr merge --squash` を直接叩かない** — 運用ロジックが `scripts/merge_pr.py` に集約されているため、生コマンドを叩くと片付けが抜ける。

## 使う場面

- 段階 4 (`4_create_pr.md`) で PR を Draft → Ready に切り替え、CI が緑になった後
- レビュー指摘への追加対応も済み、squash merge して良い状態のとき
- `auto_run_issue.md` のフローから親セッションが呼び出すとき

## 入力

- 対象 PR 番号 `<N>`
- PR が **Ready** であること
- CI が **すべて success** であること
- 自己レビュー or independent reviewer agent によるレビュー完了

## 前提

以下を満たさないと `make merge-pr` が中断する（保守的に止まる設計）:

- PR の state が `OPEN`（`MERGED` / `CLOSED` ではない）
- mergeable 状態が `MERGEABLE`（`CONFLICTING` ではない）
- statusCheckRollup の全チェックが `SUCCESS`

不備があれば段階 4 に戻って原因を潰す。

## 実施手順

1. **PR の状態を最終確認する**
   ```bash
   gh pr checks <N>
   gh pr view <N> --json state,mergeable,statusCheckRollup
   ```
   - 全チェックが `success` であることを目視確認
   - mergeable が `MERGEABLE / CLEAN` であること

2. **`make merge-pr PR=<N>` を実行する**
   ```bash
   # リポジトリ直下または worktree 内のどちらからでも可
   make merge-pr PR=<N>

   # 内容を確認だけしたい場合（実コマンドは走らない）
   make merge-pr PR=<N> DRY_RUN=1
   ```
   `make merge-pr` の内部で実行されるステップ（`scripts/merge_pr.py`）:
   1. PR 状態確認（state / mergeable / statusCheckRollup）— CI 未通過なら中断
   2. `gh pr ready <N>` — Draft → Ready 切替（Ready 済なら no-op）
   3. `gh pr merge <N> --squash --delete-branch` — squash merge とリモートブランチ削除
   4. headRefName から worktree path を導出
   5. `git worktree remove gitworktree/feature-<N>-<keyword>` — 不在なら warning で続行
   6. `git branch -D feature/<N>-<keyword>` — 不在なら warning で続行
   7. `git checkout develop && git pull --ff-only` — develop を最新化

3. **手動で実行する場合（fallback）**
   `make merge-pr` が使えない（壊れた・SCM 環境差異）など例外時のみ、以下を **同じ順番で** 実行する:
   ```bash
   gh pr ready <N>
   gh pr merge <N> --squash --delete-branch
   cd <repo_root>
   git worktree remove gitworktree/feature-<N>-<keyword>
   git branch -D feature/<N>-<keyword>
   git checkout develop
   git pull --ff-only
   ```
   詳細は [`docs/rules/git-worktree.md`](../../docs/rules/git-worktree.md) §3.5 の `<details>` 節を参照。

4. **Issue が auto-close されたか確認する**
   - PR 本文に `Closes #<N>` がある場合、merge 時に Issue が自動 close する
   - されていなければ明示的に: `gh issue close <N> --comment "PR #<PR番号> で merge 済"`

5. **完了報告**
   - PR URL、merged commit hash（`git log develop -1 --oneline` で確認）
   - 削除した worktree パスと branch 名
   - Issue が closed になったかどうか

## 出力物

- merged PR（`gh pr view <N> --json state` が `MERGED`）
- 片付け済の worktree（`git worktree list` に該当行なし）
- closed な Issue（PR の `Closes #<N>` で auto-close）

## 完了条件

- [ ] PR が `MERGED` になっている
- [ ] `git worktree list` に該当 worktree がない
- [ ] `git branch --list feature/<N>-*` が空
- [ ] develop ブランチが merged commit を含んで最新化されている
- [ ] Issue が `closed`（auto-close または明示 close）

## 注意点

- **`make merge-pr` を使う**。`gh pr merge --squash` を直接叩くと worktree 片付けが抜けて、後で `git worktree list` に幽霊が残る
- **Draft 状態のまま `gh pr merge` を叩くとエラー**。`make merge-pr` は内部で `gh pr ready` を先に叩くので問題ないが、手動 fallback では順序を守る
- **CI が落ちた状態で merge しない**。`make merge-pr` は中断するので、無理やり進めようとしない
- **`-D`（強制削除）を使うのは squash merge 後のみ**。squash merge は履歴上 fast-forward にならないため、ローカルブランチは「未マージ」と判定される。これは想定内
- **複数 PR を並列 merge する場合の順序**は [`docs/rules/git-worktree.md`](../../docs/rules/git-worktree.md) §3.5「並列 PR merge の順序」に従う

## 関連

- [`4_create_pr.md`](4_create_pr.md) — PR 作成 → Draft → Ready 化までを担当
- [`docs/rules/git-worktree.md`](../../docs/rules/git-worktree.md) §3.5 — 定型フロー詳細
- [`docs/rules/branch-strategy.md`](../../docs/rules/branch-strategy.md) §5 — squash merge の運用根拠
- `scripts/merge_pr.py` — `make merge-pr` の実体
- `Makefile` — `make merge-pr` ターゲット定義
