---
name: subagent_prompt_template
description: sub-agent に渡すプロンプトの必須要素 A〜E と、用途別（implementer / reviewer）コピペ可能雛形。
---

# SKILL: subagent_prompt_template — sub-agent プロンプト雛形集

## 目的

親セッション（PM）が sub-agent に作業を委譲するときに渡す **プロンプトの必須要素と用途別雛形** を集約する。
プロンプト不備が原因で起きた事故（PR #17/#18 の `pyright src/` 部分検査、Issue #27/#29 の self-stall timeout、worktree 命名違反など）の再発防止が目的。

行動規範や監視ロジックは [`pm_sop.md`](pm_sop.md) に分離されている。本ファイルは **プロンプトの中身に何を書くか** だけを扱う。

## 使う場面

- 親セッションが sub-agent (general-purpose) に Issue 単位の作業を委譲するとき
- `auto_run_issue.md` のフロー §3 (impl) / §4 (review) で sub-agent を起動するとき
- 既存 PR への追加対応を sub-agent に依頼するとき

---

## 必須要素 A〜E

すべての sub-agent プロンプトに以下 A〜E を **絶対パスで** 含める。

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
  - `.claude/skills/5_merge_and_cleanup.md` → merge は `make merge-pr PR=<N>` を使う。
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

---

## implementer 用雛形（コピペ可）

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
3. Issue にコメントで plan 投稿（`.claude/skills/1_issue_plan.md` を Read して従う）
4. TDD サイクルで順次実装（test → feat を別 commit、`.claude/skills/2_issue_impl.md` を Read）
5. 全検査緑（ruff / ruff format --check / pyright / pytest、`docs/rules/ci-parity.md`）
6. 自己レビューコメントを Issue に投稿（成功条件チェック表、`.claude/skills/3_review_and_refactor.md` を Read）
7. `git push -u origin feature/<N>-<keyword>` → `gh pr create --draft --base develop`、本文に `Closes #<N>`（`.claude/skills/4_create_pr.md` を Read）
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

---

## reviewer 用雛形（コピペ可）

実装者と独立した sub-agent にレビューさせるときに使う。本体コードは触らせない。

```markdown
あなたは synthpop-jp プロジェクトの **independent reviewer agent** として、GitHub Issue #<N> の実装をレビューする。

## 固定情報

- リポジトリ: <絶対パス>
- **作業ディレクトリ（読み取り専用 / コードは絶対に触らない）**: <絶対パス>/gitworktree/feature-<N>-<keyword>
- 対象ブランチ: feature/<N>-<keyword>
- base branch: develop
- Issue: https://github.com/<owner>/<repo>/issues/<N>

## 前置き: 依存する先行 PR の成果

<implementer に渡したのと同じ依存 PR 一覧>

## 入力

- Issue 本文と plan コメント: `gh issue view <N> --comments`
- diff: `git -C <作業ディレクトリ> diff develop..HEAD`
- 追加コミット履歴: `git -C <作業ディレクトリ> log develop..HEAD --oneline`
- 該当 PR（Draft で作成済）: `gh pr view <PR番号>`

## 守るべき rule

- **コードを 1 行も触らない**。`src/` も `tests/` も書き換えない
- 出力は **Issue #<N> へのコメント 1 本**。`gh issue comment <N> --body "$(cat <<'EOF' ... EOF)"` で投稿する
- レビューは [`.claude/skills/3_review_and_refactor.md`](`.claude/skills/3_review_and_refactor.md`) の観点に沿って行う
- レビューサマリの構成は [`docs/templates/review_summary.md`](`docs/templates/review_summary.md`) に従う

## レビュー観点（最低限）

1. **テスト充足**: plan で挙げたテスト観点が実装に対応しているか
2. **CI parity**: 手元 4 コマンド（ruff / ruff format --check / pyright / pytest）が緑か（コミット履歴 / CI ログから）
3. **設計負債**: 重複コード、責務混在、早すぎる抽象化、マジックナンバー
4. **可読性**: 命名、関数長、docstring が呼び出し意図を書いているか
5. **再現性**: 実験を含む場合、seed / 設定 / 出力先が固定されているか
6. **非技術者向け説明可能性**: Issue の「価値・成功条件」が満たされていると 1 段落で説明できるか
7. **Critical 指摘の有無**: merge を止めるべき問題があるか

## 出力（Issue コメントとして投稿）

```markdown
## レビューサマリ（independent reviewer agent）

### テスト結果
- 件数 / カバレッジ / 落ちた履歴

### 実装で分かったこと
- plan との差分、仕様メモ

### 実験結果の解釈（該当する場合）
- 非技術者にも通じる 1 段落

### 見つかった負債と対応提案
- 直すべき / 別 Issue 化が望ましい

### 残課題
- 次の Issue で扱うべき内容

### Critical 指摘の有無
- あり / なし（ありの場合は内容と修正範囲）

### レビュアーに見てほしい点（PR 著者向け）
- 設計判断 / 実験結果の妥当性 など
```

## 戻り値

以下を含む完了レポートを 200 語以内で返す:
- 投稿した Issue コメント URL
- Critical 指摘の有無（あり / なし）
- 主要論点 3 つ
- 「merge 可」「修正が必要」のどちらの判定か
```

---

## Agent 側の進捗報告義務

Phase 2 Wave 1 の Issue #27 と #29 で、サブエージェントが「テストをまとめて書いてから Green に進む」戦略を取り、
10 分以上 Issue コメントもコミットもなく無音になった結果 timeout 停止する事案が連続発生した。
根本原因は **Agent 側に明確な進捗報告義務がなかったこと**。
本節では義務を定める。

### plan コメントの投稿タイミング

**最初の 1 commit と同時に** Issue にコメントとして plan を投稿する。後回し禁止。

Issue #27 / #29 の事例: plan コメントを「実装が固まってから投稿しよう」と後回しにした結果、
最初の commit すら入らないまま timeout した。PM は何が起きているか把握できなかった。

```bash
# 最初の test: コミットと同時に plan を投稿する
gh issue comment <N> --body "## 実装計画
..."
git add tests/...
git commit -m "test: <first test> (refs #<N>)"
```

### 進捗コメントの頻度

**3 コミット毎、または最後のコメントから 10 分のどちらか先に達した時点** で、
Issue に 1 コメントを投稿する。

コメントの中身は 3 行以内:

```
- 何をやったか（例: WorktreeInfo dataclass と collect_worktree_info を実装）
- 想定通りだったか（例: 想定通り、または「git worktree list の行形式が予想と違いパース修正」）
- 次に何をやるか（例: IssueInfo 収集関数のテストに着手）
```

これは [`2_issue_impl.md`](2_issue_impl.md) 手順 7「節目ごとに Issue へ進捗コメントを残す」と同義。
フォーマットを固定することで PM 側の読み取りコストを下げる。

### self-stall 宣言

最終 commit から **15 分以上**、かつ進捗コメントも追加されていない状態を **self-stall** と呼ぶ。

self-stall 状態になったら、作業を中断して以下を実行する:

1. 現在の差分を中間コミットとして push（`wip:` プレフィックスでよい）
2. `gh pr create --draft --base develop --title "WIP: <branch>"` で中間 Draft PR を作成
3. Issue に「self-stall 宣言コメント」を投稿する:

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

---

## チェックリスト

プロンプトを書き上げたら、送る前に以下を確認する:

- [ ] A〜E の必須要素がすべて入っている
- [ ] 絶対パスで作業ディレクトリを指定している（相対パスは禁止）
- [ ] 依存 PR の merged commit hash を `git log develop --oneline -N` で確認した
- [ ] `pyright` を「引数なし」で要求している（`pyright src/` ではない）
- [ ] 進捗報告義務（plan / 3 コミット毎 / self-stall）を明記している
- [ ] 戻り値フォーマット（300 語以内）を指定している
- [ ] reviewer 用の場合: 「コードを 1 行も触らない」を明記している

## 関連

- [`auto_run_issue.md`](auto_run_issue.md) — 0→5 自律走破オーケストレータ
- [`pm_sop.md`](pm_sop.md) — 親セッションの行動規範
- [`2_issue_impl.md`](2_issue_impl.md) — implementer 側の手順詳細
- [`3_review_and_refactor.md`](3_review_and_refactor.md) — reviewer 側の観点詳細
