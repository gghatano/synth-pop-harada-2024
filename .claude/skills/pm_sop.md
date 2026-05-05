---
name: pm_sop
description: 親セッション（PM 役）が複数 Issue を sub-agent に委譲しながら進めるときの行動規範。委譲の判断、監視、失敗復旧、DoD 検証。
---

# SKILL: pm_sop — 親セッションの行動規範（PM SOP）

## 目的

Phase が進むにつれて 1 Phase 内で 3〜6 Issue を並列に回す必要が出てくる。
単に並列に sub-agent を呼ぶだけでは:

- サブエージェントが先行 PR の API を把握できず、develop の古い HEAD を参照する
- `1_issue_plan` / `3_review_and_refactor` の Issue コメント投稿を省略する
- worktree を自前で作ってルールに合わない場所に置く

といった事故が起きる。本 skill は **親セッション（PM 役）の行動規範** をまとめる。
プロンプト雛形そのものは [`subagent_prompt_template.md`](subagent_prompt_template.md) に分離されている。

## 使う場面

- 1 Phase で 3 本以上の Issue を並列・直列に回すとき
- 既存 PR の API に依存する新 Issue のサブエージェントを起動するとき
- 長時間かかる実装をバックグラウンド agent に任せるとき
- `auto_run_issue.md` が複数 Issue を順繰りに走らせるとき

## 親セッションの責務

サブエージェントを起動する前に、以下 5 点を **親セッション側で済ませる**:

1. **Issue を value_driven テンプレで起票** する（[`0_issue_create.md`](0_issue_create.md) に従う）。サブエージェントは起票しない
2. **worktree を作成** する（`develop` 起点、命名規則は [`docs/rules/git-worktree.md`](../../docs/rules/git-worktree.md)）
3. **worktree で `uv sync --frozen` と baseline 検査**（pytest / pyright）を走らせて green を確認
4. **依存 PR の merged commit hash と使える API を整理** する
5. サブエージェントに渡すプロンプトに必須要素 A〜E を **絶対パスで** 含める（雛形は [`subagent_prompt_template.md`](subagent_prompt_template.md)）

## 委譲の判断

### 並列起動の条件

- 2 つ以上の Issue が **直接の依存を持たない**（一方の PR が merged にならなくても他方が始められる）
- 変更ファイルに明確な重複がない（`src/` の同一ファイルを 2 エージェントが同時に触るのは避ける）
- 親セッションが **両方の monitor を並行して回せる**（`Monitor` tool）

### 直列にすべき条件

- Issue B の plan / impl で Issue A の API を前提にしている
- 同一モジュール（`cli.py`, `config.py` など）を両方が変更する可能性がある

### 重実験 worktree が active な間は新規 Agent を起動しない

Issue #51 の実測（2026-04-29）で、SA 単独は 100k 世帯でも 358MB であり物理 RAM を圧迫しないと判明した。
PC が固まる事故は **「重実験 + 並列 Agent + ブラウザ等」の合算** で物理 RAM が枯渇したときに起きる。
本節は再発防止の運用ルール:

- worktree 内に `experiments/*/WEIGHT.md` で `heavy` を宣言した実験ディレクトリがある場合、その worktree は「重実験 worktree」
- **重実験 worktree が 1 本でも active な間、新規 Agent の起動を控える**
- `make pm` の出力で確認できる（worktree 行に `⚠ heavy`）
- 暫定しきい値: **N ≥ 100k 世帯の SA を含む実験は heavy**（Issue #51 実測値による）。
  実験ディレクトリに `WEIGHT.md` を置くこと（`light` または `heavy` を 1 行）

詳細は [`docs/rules/experiment-management.md`](../../docs/rules/experiment-management.md) §4「重さタグ（WEIGHT.md）」を参照。

### 例: Phase 1 の実行順序

```
Issue #12 (data contract)                          # 先行、他 4 つの土台
  └─ merge
     ├─ Issue #13 (PopulationArrays)  ┐            # #12 に依存、両者は独立
     └─ Issue #16 (SeedRegistry)      ┘ 並列可
        └─ いずれか merge
           └─ Issue #14 (initial population)       # #13 と #16 両方を利用
              └─ merge
                 └─ Issue #15 (quickstart CLI)     # #14 を利用
```

## 監視ループ

サブエージェントを `run_in_background: true` で起動したら:

1. 完了通知（task-notification）を待つ。**polling や output file の tail はしない**
2. 進捗確認が必要なら **worktree の `git log origin/develop..HEAD` と `git diff --stat`** で代替する
3. 完了したら:
   - worktree 内で手元 CI 4 コマンドを走らせる（[`docs/rules/ci-parity.md`](../../docs/rules/ci-parity.md) §2 の 4 コマンド）
   - GitHub CI 結果を `gh pr checks <N>` で確認（`Monitor` tool で失敗時に通知を受ける）
   - 失敗していれば原因を最小修正して push、再度 CI を待つ
   - 緑になったら `gh pr ready <N>` → `make merge-pr PR=<N>`（[`5_merge_and_cleanup.md`](5_merge_and_cleanup.md) 参照）

### `make pm` による観測

```bash
# 全 active worktree の状態を 1 画面で確認
make pm

# Phase 2 の Issue に絞り、stale 閾値を 15 分に変更
make pm ARGS="--phase 2 --stale-minutes 15"

# JSON で機械可読出力
make pm ARGS="--json"
```

stale 閾値: 最終 commit から 10 分で 🟡 警告、20 分で 🔴 危険マーク。

## 失敗復旧フロー

| 失敗 | 自律対応 | 諦めライン |
|---|---|---|
| CI 落ち（lint / format） | sub-agent に修正タスク再委譲（diff + 失敗ログ付き） | 2 回 |
| pyright / pytest 落ち | sub-agent に修正タスク再委譲（diff + 失敗ログ付き） | 2 回 |
| Independent review が Critical 指摘 | 修正タスク再委譲 | 1 回 |
| conflict | 親が `git rebase origin/develop` で解決、解決不能なら user に報告 | 1 回 |
| sub-agent self-stall（10 分無音） | 中間 commit + WIP draft PR + 親が引き継ぐ | 即時 |
| 依存 PR 未 merge で待機 | 親が依存 PR の `make merge-pr` を先に走らせる、または直列に並べ替え | 即時 |

諦めラインを超えたら user にエスカレーション。沈黙して諦めない。

## 親セッションの DoD（Issue ごと）

1 Issue を「次に進める」と判断する前に以下が揃っていることを確認する:

- [ ] サブエージェントに A〜E の必須要素を含むプロンプトを渡した（[`subagent_prompt_template.md`](subagent_prompt_template.md)）
- [ ] 依存 PR の merged commit hash を `git log` で確認してからプロンプトに記載した
- [ ] 並列起動した場合、各 Agent の作業ディレクトリが別 worktree になっている
- [ ] 完了通知を待つ間、親セッションは他 Issue の準備か user への進捗報告に専念
- [ ] サブエージェントが残した plan / review コメントを Issue 上で確認した
- [ ] 手元 CI 4 コマンドが緑（[`docs/rules/ci-parity.md`](../../docs/rules/ci-parity.md)）
- [ ] PR が merged、worktree 片付け済み（[`5_merge_and_cleanup.md`](5_merge_and_cleanup.md)）

## 注意点

- **プロンプトから短縮語を減らす**。「plan を投稿」ではなく「`gh issue comment <N> --body ...` で plan を Issue コメントとして投稿」と具体的に書く
- **pyright の引数なし実行を明示的に要求**。「pyright が通ること」ではなく「`uv run pyright`（引数なし）が 0 errors」と書かないと、サブエージェントは `pyright src/` で済ませる
- **サブエージェントに Agent を再帰起動させない**。階層が深くなると管理不能になる。本 skill は親セッション 1 階層のみを想定
- **失敗の責任は親セッションにある**。CI 失敗はサブエージェントのプロンプト不足か親セッションの監視不足のどちらかとして振り返る

## 関連

- [`auto_run_issue.md`](auto_run_issue.md) — 0→5 自律走破オーケストレータ（PM の上位呼び出し元）
- [`subagent_prompt_template.md`](subagent_prompt_template.md) — sub-agent プロンプト雛形（A〜E 必須要素 + コピペ可）
- [`5_merge_and_cleanup.md`](5_merge_and_cleanup.md) — merge と片付けの専任 skill
