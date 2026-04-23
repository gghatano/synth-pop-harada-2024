# 開発ワークフロー入門

本ドキュメントは、本リポジトリで **最初に作業する人が迷わないように** するためのガイドです。
詳細なルールは各所に分かれていますが、このページ 1 枚で全体像を掴み、最初の Issue を進められることを目標にします。

---

## 0. 最初に読むもの（15 分）

以下の順で目を通してください。

1. [`CLAUDE.md`](../../CLAUDE.md)（中核ルール。3 分で読める）
2. 本ドキュメント（全体フローの把握）
3. [`docs/rules/issue-driven-development.md`](../rules/issue-driven-development.md)（Issue の書き方）

深く追う前に、この 3 つをざっと流し読みして全体像を掴むのが早道です。詳細は後で必要になったときに引けばよい。

---

## 1. 全体フロー（0 → 4）

1 つの Issue は必ず次の 5 段階を通ります。

```
段階 0: 0_issue_create         → 価値起点で Issue を作る
段階 1: 1_issue_plan           → 設計・テスト・実験計画を Issue に記録
段階 2: 2_issue_impl           → TDD で実装、実験を走らせる
段階 3: 3_review_and_refactor  → 自己レビュー、リファクタ、HTML レポート化
段階 4: 4_create_pr            → develop 向け PR
```

各段階の詳細は `.claude/skills/` 配下。Claude Code 上では `/0_issue_create` のように呼び出せます。

---

## 2. Issue の作り方（段階 0）

1. 「誰に・どんな価値を」を 1 文で書けるまで考える
2. テンプレート [`.github/ISSUE_TEMPLATE/feature_value_driven.md`](../../.github/ISSUE_TEMPLATE/feature_value_driven.md) で Issue を作成
3. タイトル形式: `[phase-<番号>] <価値を示す短い動詞句>`

### 例

> **タイトル**: `[phase-1] 研究者が 100 万人規模の合成人口を 1 時間以内で生成できるようにする`

**実装方法や使うライブラリは Issue 本文に書かない**。それらは段階 1 で扱います。

詳細: [`docs/rules/issue-driven-development.md`](../rules/issue-driven-development.md) / [`.claude/skills/0_issue_create.md`](../../.claude/skills/0_issue_create.md)

---

## 3. ブランチと worktree の切り方（段階 1 の冒頭）

開発はすべて worktree 上で行います。**リポジトリ直下で直接編集しない**。

```bash
# リポジトリ直下で
git fetch origin
git worktree add -b feature/42-add-sa-core gitworktree/feature-42-add-sa-core origin/develop
cd gitworktree/feature-42-add-sa-core
```

- worktree ディレクトリ: `<repo_root>/gitworktree/feature-<issue番号>-<keyword>/`
- ブランチ: `feature/<issue番号>-<keyword>`
- 起点: 必ず `origin/develop`

詳細: [`docs/rules/git-worktree.md`](../rules/git-worktree.md) / [`docs/rules/branch-strategy.md`](../rules/branch-strategy.md)

---

## 4. 計画の書き方（段階 1）

worktree を作ったら、コードを書き始める前に計画を立てます。テンプレ: [`docs/templates/issue_plan.md`](../templates/issue_plan.md)。

最低限含めるもの:

- 設計方針（何を変え、何を変えないか）
- 実装方針（ファイル単位で）
- テスト観点（単体 / 結合 / 回帰 / 性質）
- 実験計画（伴う場合。仮説・条件・指標・判定基準）
- リスクと代替案

計画は Issue コメントに投稿するか、長ければ `docs/plans/issue-<番号>.md` として別ファイルにします。

詳細: [`.claude/skills/1_issue_plan.md`](../../.claude/skills/1_issue_plan.md)

---

## 5. TDD で実装する（段階 2）

1. **Red**: 落ちるテストを 1 つ書く（実行して赤になることを確認）
2. **Green**: 最小実装でテストを通す
3. **Refactor**: テストは green のまま整理する

1 サイクルは小さく保つ（数十行〜200 行）。1 日分の作業を 1 コミットにまとめない。

```bash
# サイクルの例
# Red
git add tests/unit/test_sa.py
git commit -m "test: SA delta apply preserves origin array (refs #42)"

# Green
git add src/optimize/delta.py
git commit -m "feat: add delta.apply for SA iteration (refs #42)"

# Refactor
git add src/optimize/
git commit -m "refactor: extract Pop dtype into types module (refs #42)"
```

探索的な実験コードは `experiments/<日付>-<slug>/` に分離し、本体には入れない。

詳細: [`docs/rules/tdd.md`](../rules/tdd.md) / [`.claude/skills/2_issue_impl.md`](../../.claude/skills/2_issue_impl.md)

---

## 6. 実験結果の残し方（段階 2 / 3）

実験は `experiments/<YYYY-MM-DD>-<slug>/` 配下で行い、結果は Markdown → HTML の両方で残します。

```
experiments/2026-04-23-sa-convergence-baseline/
  report.md        # 編集する実体（テンプレ: docs/templates/experiment_report.md）
  report.html      # HTML 化したもの（閲覧用）
  config.yaml      # seed・条件
  data/INPUT.md    # 使用データのバージョン
  output/          # ログ・指標・図
```

必ず含める:

- seed（config 固定）
- 使用データのバージョン
- コミット SHA
- 非技術者向け要約（5 行）
- 再現手順（1 コマンド）
- 制約
- 次アクション

失敗実験も捨てずに記録する。

詳細: [`docs/rules/experiment-management.md`](../rules/experiment-management.md) / [`docs/rules/html-reporting.md`](../rules/html-reporting.md)

---

## 7. 自己レビュー（段階 3）

実装が一段落したら、PR を出す前に自分で自分のコードを読み直します。

- 全テスト green を確認
- `git diff develop..HEAD` を他人の目で読み直す
- 設計負債（重複・責務混在・マジックナンバー）の棚卸し
- 非技術者に 1 段落で説明できるか確認
- 再現手順が実際に通るか確認

結果をレビューサマリ（[`docs/templates/review_summary.md`](../templates/review_summary.md)）として Issue コメントに投稿。

詳細: [`.claude/skills/3_review_and_refactor.md`](../../.claude/skills/3_review_and_refactor.md)

---

## 8. PR を作る（段階 4）

```bash
# develop を取り込んでコンフリクトを解消
git fetch origin
git rebase origin/develop
uv run pytest

# PR 作成（テンプレは .github/pull_request_template.md を自動読み込み）
gh pr create --base develop --draft \
  --title "[#42] 研究者が SA で 100 万人規模の合成人口を生成できるようにする"
```

PR 本文で埋めるべき欄:

- 背景
- 提供する価値
- 変更内容（論理単位）
- 影響範囲
- テスト結果
- 実験結果（HTML レポートへのリンク）
- 残課題
- レビュアーに見てほしい点

CI が green になったら Draft → Ready に切り替え、レビュアーを指名します。

詳細: [`.claude/skills/4_create_pr.md`](../../.claude/skills/4_create_pr.md) / [`docs/rules/branch-strategy.md`](../rules/branch-strategy.md)

---

## 9. merge 後の後片付け

```bash
cd <repo_root>
git worktree remove gitworktree/feature-42-add-sa-core
git branch -d feature/42-add-sa-core
```

対応 Issue は `Closes #42` で自動 close されるはず。されなければ手動で close。

---

## 10. 困ったとき

| 症状 | 参照先 |
|---|---|
| Issue の書き方が分からない | [`docs/rules/issue-driven-development.md`](../rules/issue-driven-development.md) |
| worktree をどう切るか | [`docs/rules/git-worktree.md`](../rules/git-worktree.md) |
| rebase でコンフリクトした | [`docs/rules/branch-strategy.md`](../rules/branch-strategy.md) §4 |
| テストをどこに置くか | [`docs/rules/tdd.md`](../rules/tdd.md) §4 |
| 実験結果の書き方 | [`docs/rules/experiment-management.md`](../rules/experiment-management.md) / [`docs/templates/experiment_report.md`](../templates/experiment_report.md) |
| HTML レポートの作り方 | [`docs/rules/html-reporting.md`](../rules/html-reporting.md) |
| 文体で迷う | [`docs/rules/documentation-style.md`](../rules/documentation-style.md) |
| PR 本文を何に使うか | [`.github/pull_request_template.md`](../../.github/pull_request_template.md) |

---

## 11. チェックリスト（初回作業時）

- [ ] `CLAUDE.md` を読んだ
- [ ] このページを読んだ
- [ ] `docs/rules/issue-driven-development.md` を読んだ
- [ ] 最初の Issue のタイトルを「価値起点」で書けた
- [ ] worktree を `gitworktree/feature-...` に作れた
- [ ] 計画を Issue コメントに貼れた
- [ ] 最初のテストを書いて赤にできた

ここまで通れば、あとは段階 2 以降を小さく回すだけです。
