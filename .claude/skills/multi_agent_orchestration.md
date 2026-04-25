---
name: multi_agent_orchestration
description: 複数 Issue を並列に進めるために、Claude Code の親セッションがサブエージェント（Task tool / Agent tool）を呼び分けるときの運用を定める。プロンプト雛形と依存関係の受け渡しを含む。
---

# SKILL: multi_agent_orchestration — サブエージェント並列実行の運用

## 目的

Phase が進むにつれて 1 Phase 内で 3〜6 Issue を並列に回す必要が出てくる。単に並列に `Agent` tool を呼ぶだけでは、

- サブエージェントが先行 PR の API を把握できず、develop の古い HEAD を参照する
- `1_issue_plan` / `3_review_and_refactor` の Issue コメント投稿を省略する
- worktree を自前で作ってルールに合わない場所に置く

といった事故が起きる。本 skill は、**親セッションがサブエージェントに渡すプロンプトに必ず入れるべき要素** をまとめる。

## 使う場面

- 1 Phase で 3 本以上の Issue を並列・直列に回すとき
- 既存 PR の API に依存する新 Issue のサブエージェントを起動するとき
- 長時間かかる実装をバックグラウンド agent に任せるとき

## 親セッションの責務

サブエージェントを起動する前に、以下 5 点を **親セッション側で済ませる**:

1. **Issue を value_driven テンプレで起票** する（`.claude/skills/0_issue_create.md` に従う）。サブエージェントは起票しない
2. **worktree を作成** する（`develop` 起点、命名規則は `docs/rules/git-worktree.md`）
3. **worktree で `uv sync --frozen` と baseline 検査**（pytest / pyright）を走らせて green を確認
4. **依存 PR の merged commit hash と使える API を整理** する
5. サブエージェントに渡すプロンプトに以下を**絶対パスで**含める

## サブエージェントプロンプトに含める必須要素

### A. 固定情報ブロック

```
- リポジトリ: <絶対パス>
- **作業ディレクトリ（必ずこの worktree 内で作業する）**: <絶対パス>
- ブランチ: feature/<N>-<keyword>（origin/develop 起点、worktree 作成済、uv sync 済、<baseline テスト数> passed / pyright 0 errors を確認済）
- base branch: develop
- Issue: https://github.com/<owner>/<repo>/issues/<N>
- Issue 本文（スコープ / 成功条件 / 非スコープ）は `gh issue view <N>` で読める。すべてそこに書かれている前提を守る。
```

### B. 依存する先行 PR の成果

```
## 前置き: 依存する先行 PR の成果（すべて develop に merged 済）

### Issue #<A> merged (commit <hash>)
- `<使えるモジュールパス>`: 提供 API の 1 文説明
- ...

### Issue #<B> merged (commit <hash>)
- ...
```

サブエージェントは `git log` から依存を推定する代わりに、**この節をそのまま信じて実装する**。
親セッションは直前の `git log develop --oneline -N` で hash を確認する。

### C. 守るべき rule の明示列挙

最低でも以下を列挙する:

```
- `CLAUDE.md` と `docs/rules/{tdd,issue-driven-development,branch-strategy,git-worktree,ci-parity,documentation-style}.md` に従う。
- skill 運用:
  - `.claude/skills/1_issue_plan.md` → plan を **Issue #<N> のコメント**として投稿。docs/plans に別ファイルは作らない。
  - `.claude/skills/2_issue_impl.md` → TDD で Red → Green → Refactor、test と feat は別 commit。
  - `.claude/skills/3_review_and_refactor.md` → 自己レビューサマリを Issue #<N> にコメントで投稿。
  - `.claude/skills/4_create_pr.md` → develop 向け Draft PR を作成、本文末尾に `Closes #<N>`。
- **TDD 厳守**。新振る舞いには先に落ちるテスト。
- commit は Claude Opus 4.7 の Co-Authored-By trailer を含めて署名（HEREDOC）。
- hooks skip 禁止（--no-verify）。
- **CI と同じ順で手元検査**: `uv run ruff check .` → `uv run ruff format --check .` → `uv run pyright`（src+tests）→ `uv run pytest`。詳細は `docs/rules/ci-parity.md`。
- 非スコープ（Issue 明記）には手を出さない。
```

### D. 想定規模と分割判断基準

```
## 想定規模

<N>〜<M> 行の実装 + <X>〜<Y> 行のテスト。これより膨らむなら非スコープに逃がす判断をして plan comment を更新する。
```

「想定規模」は親セッションが Issue 本文とコードベースの読みから立てる見積り。
**実装中に規模が倍を超えそうなら、サブエージェントは plan comment を更新し、親セッションに報告する**。

### E. 戻り値フォーマット

```
## 戻り値

以下を含む完了レポートを 300 語以内で返す:
- PR URL
- 追加・変更ファイル（合計数と主要な行）
- 合計コミット数、テスト数
- 未解決の論点 / レビュー依頼事項
- CI（もし手元で走らせたもの）の結果
```

短い固定フォーマットで戻すことで、親セッションのコンテキストが膨れない。

## 並列起動の判断

### 並列可能な条件

- 2 つ以上の Issue が **直接の依存を持たない**（一方の PR が merged にならなくても他方が始められる）
- 変更ファイルに明確な重複がない（`src/` の同一ファイルを 2 エージェントが同時に触るのは避ける）
- 親セッションが **両方の monitor を並行して回せる**（Monitor tool）

### 直列にすべき条件

- Issue B の plan / impl で Issue A の API を前提にしている
- 同一モジュール（`cli.py`, `config.py` など）を両方が変更する可能性がある

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

## Agent 側の進捗報告義務

Phase 2 Wave 1 の Issue #27 と #29 で、サブエージェントが「テストをまとめて書いてから Green に進む」戦略を取り、
10 分以上 Issue コメントもコミットもなく無音になった結果 timeout 停止する事案が連続発生した。
根本原因は **Agent 側に明確な進捗報告義務がなかったこと**。
本節では義務を定める。

### plan コメントの投稿タイミング

**最初の 1 commit と同時に** Issue にコメントとして plan を投稿する。後回し禁止。

Issue #27 / #29 の事例：plan コメントを「実装が固まってから投稿しよう」と後回しにした結果、
最初の commit すら入らないまま timeout した。PM は何が起きているか把握できなかった。

```bash
# 最初の test: コミットと同時に plan を投稿する
gh issue comment <N> --body "## 実装計画
..."
git add tests/...
git commit -m "test: <first test> (refs #<N>)"
```

### 進捗コメントの頻度

**3 コミット毎、または最後のコメントから 10 分のどちらか先に達した時点**で、
Issue に 1 コメントを投稿する。

コメントの中身は 3 行以内：

```
- 何をやったか（例: WorktreeInfo dataclass と collect_worktree_info を実装）
- 想定通りだったか（例: 想定通り、または「git worktree list の行形式が予想と違いパース修正」）
- 次に何をやるか（例: IssueInfo 収集関数のテストに着手）
```

これは `.claude/skills/2_issue_impl.md` 手順 7「節目ごとに Issue へ進捗コメントを残す」と同義。
フォーマットを固定することで PM 側の読み取りコストを下げる。

### self-stall 宣言

最終 commit から **15 分以上**、かつ進捗コメントも追加されていない状態を **self-stall** と呼ぶ。

self-stall 状態になったら、作業を中断して以下を実行する：

1. 現在の差分を中間コミットとして push（`wip:` プレフィックスでよい）
2. `gh pr create --draft --base develop --title "WIP: <branch>"` で中間 Draft PR を作成
3. Issue に「self-stall 宣言コメント」を投稿する：

   ```
   ## self-stall 宣言（PM 報告）
   - 最終 commit から 15 分以上停止
   - 現状: <何ができていて何が詰まっているか>
   - 原因仮説: <詰まり原因>
   - 要判断: <PM に判断を求めること、または次のアクション>
   ```
4. 完了報告を返す（PM がセッションを引き継ぐ）

PM 側は `make pm` または `uv run python scripts/pm_status.py` で stale worktree を検知できる
（最終 commit から 10 分で 🟡 警告、20 分で 🔴 危険マーク）。

### PM による観測

```bash
# 全 active worktree の状態を 1 画面で確認
make pm

# Phase 2 の Issue に絞り、stale 閾値を 15 分に変更
make pm ARGS="--phase 2 --stale-minutes 15"

# JSON で機械可読出力
make pm ARGS="--json"
```

## 親セッションの監視ループ

サブエージェントを `run_in_background: true` で起動したら:

1. 完了通知（task-notification）を待つ。**polling や output file の tail はしない**
2. 進捗確認が必要なら **worktree の `git log origin/develop..HEAD` と `git diff --stat`** で代替する
3. 完了したら:
   - worktree 内で手元 CI 4 コマンドを走らせる
   - GitHub CI 結果を `gh pr checks <N>` で確認（`Monitor` tool で失敗時に通知を受ける）
   - 失敗していれば原因を最小修正して push、再度 CI を待つ
   - 緑になったら `gh pr ready <N>` → `gh pr merge <N> --squash --delete-branch`
   - worktree を片付ける（`docs/rules/git-worktree.md` §3.5）

## 完了条件

- [ ] サブエージェントに A〜E の必須要素を含むプロンプトを渡した
- [ ] 依存 PR の merged commit hash を `git log` で確認してからプロンプトに記載した
- [ ] 並列起動した場合、各 Agent の作業ディレクトリが別 worktree になっている
- [ ] 完了通知を待つ間、親セッションは他 Issue の準備か user への進捗報告に専念
- [ ] サブエージェントが残した plan / review コメントを Issue 上で確認した

## 注意点

- **プロンプトから短縮語を減らす**。「plan を投稿」ではなく「`gh issue comment <N> --body ...` で plan を Issue コメントとして投稿」と具体的に書く
- **pyright の引数なし実行を明示的に要求**。「pyright が通ること」ではなく「`uv run pyright`（引数なし）が 0 errors」と書かないと、サブエージェントは `pyright src/` で済ませる
- **サブエージェントに Agent を再帰起動させない**。階層が深くなると管理不能になる。本 skill は親セッション 1 階層のみを想定
- **失敗の責任は親セッションにある**。CI 失敗はサブエージェントのプロンプト不足か親セッションの監視不足のどちらかとして振り返る

## プロンプト雛形（コピー用）

```markdown
あなたは synthpop-jp プロジェクトの <ロール> として、GitHub Issue #<N>「<タイトル>」を 5 段階フローで実装する。

## 固定情報

- リポジトリ: <絶対パス>
- **作業ディレクトリ**: <絶対パス>/gitworktree/feature-<N>-<keyword>
- ブランチ: feature/<N>-<keyword>（origin/develop 起点、worktree 作成済、uv sync 済、<X> passed / pyright 0 errors 確認済）
- base branch: develop
- Issue: https://github.com/<owner>/<repo>/issues/<N>

## 前置き: 依存する先行 PR の成果（すべて develop に merged 済）

<依存先 PR の列挙。使える API とモジュールパス>

## 守るべき rule

<上記 C. ルール列挙をそのまま>

## 実装範囲

<Issue のスコープ節を再掲>

## 手順

1. `gh issue view <N>` で Issue を読み直す
2. 依存 spec / ADR を読む
3. Issue にコメントで plan 投稿（`1_issue_plan.md` 準拠）
4. TDD サイクルで順次実装（test → feat を別 commit）
5. 全検査緑（ruff / ruff format --check / pyright / pytest、`docs/rules/ci-parity.md`）
6. 自己レビューコメントを Issue に投稿（成功条件チェック表）
7. `git push -u origin feature/<N>-<keyword>` → `gh pr create --draft --base develop`、本文に `Closes #<N>`
8. 完了報告（上記 E のフォーマット）

## 作業ディレクトリ

すべて worktree 内。`cd <絶対パス>/gitworktree/feature-<N>-<keyword> && <command>` か `git -C <worktree>`。develop/main で直接編集禁止。他 worktree に触らない。

## 想定規模

<N>〜<M> 行の実装 + <X>〜<Y> 行のテスト。

## 進捗報告義務

- 最初の commit と同時に plan コメントを Issue #<N> に投稿（後回し禁止、#27/#29 の timeout 事例を反省）
- 3 コミット毎 or 10 分毎に 1 行進捗コメント（何をやったか / 想定通りか / 次は何か）
- 最終 commit から 15 分停止で中間 Draft PR 作成 + self-stall 宣言コメント + 完了報告
- PM は `make pm` で stale 検知（10 分 🟡 / 20 分 🔴）
```
