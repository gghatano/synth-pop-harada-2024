---
name: 4_create_pr
description: 自己レビュー済みの変更を `develop` 向けの PR にする。価値・変更内容・テスト・実験結果・残課題・HTML レポート導線を埋めて、レビュアーが読みやすい形にする。
---

# SKILL: 4_create_pr — develop 向け PR を作る

## 目的

段階 3 までに整えた変更を、レビュー可能な PR に仕上げる。
**PR 本文は Issue の要約ではなく、レビュアーへのガイド** として書く。「どこから読むと効率的か」「何を特に判断してほしいか」を明示する。

## 使う場面

- `3_review_and_refactor` のレビューサマリを Issue に貼り終えた後
- レビューを受けて追加対応し、再 PR する場合も本 skill を通す（テンプレ項目の抜けを防ぐため）

## 入力

- レビューサマリ済みの Issue
- 自己レビューまで済んだ feature ブランチ

## 実施手順

1. **develop を取り込んでコンフリクトを解消しておく**
   ```bash
   git fetch origin
   git rebase origin/develop      # もしくは merge。方針は branch-strategy.md に従う
   uv run pytest                  # rebase 後にテストが通ることを確認
   ```
   詳細: [`docs/rules/branch-strategy.md`](../../docs/rules/branch-strategy.md)
2. **実験レポートを HTML 化する**
   - 実験を伴った PR では、`experiments/<...>/report.md` を HTML に変換して `experiments/<...>/report.html` として置く
   - HTML レポートは PR 本文にリンクする（後述）
   - 詳細: [`docs/rules/html-reporting.md`](../../docs/rules/html-reporting.md)
3. **PR を作成する**
   ```bash
   gh pr create --base develop --draft \
     --title "[#<issue番号>] <価値を示す短い動詞句>" \
     --body "$(cat <<'EOF'
   <テンプレートに従って本文を書く>
   EOF
   )"
   ```
   テンプレートは [`.github/pull_request_template.md`](../../.github/pull_request_template.md) を使う（`gh pr create` は自動読み込みする場合あり）
4. **PR 本文の必須項目を埋める**
   - 背景
   - この変更で提供する価値
   - 変更内容（ファイル単位ではなく、論理単位で）
   - 影響範囲（他モジュール・他 Issue への波及）
   - テスト結果（件数・カバレッジ・手動確認の有無）
   - 実験 / 検証結果（HTML レポートへのリンクを含める）
   - 残課題（別 Issue を立てた場合は番号を書く）
   - レビュアーに特に見てほしい点
5. **Draft → Ready に切り替える**
   - CI（テスト・lint・型チェック）が全部通ってから Ready にする
   - Ready 切り替えと同時に、レビュアーを指名する
6. **レビューコメントへの対応ループ**
   - 指摘を受けたら feature ブランチに commit する（force push は基本しない）
   - コメントに返信する際、対応コミット SHA を添える
   - 追加実装があれば段階 2 / 3 に戻り、再度自己レビューしてから Ready 更新
7. **merge 後の後片付け**
   - merge 完了後、ローカルの worktree を削除
     ```bash
     cd <repo_root>
     git worktree remove gitworktree/feature-<issue番号>-<keyword>
     git branch -d feature/<issue番号>-<keyword>
     ```
   - 対応 Issue を close（PR 本文に `Closes #<番号>` を書いていれば自動 close される）
   - HTML レポートの公開場所（もしあれば）にデプロイするコマンドを実行

## 出力物

- `develop` 向けの PR（テンプレの全欄が埋まっている）
- HTML 化された実験レポート（該当 PR のみ）
- 残課題を分離した場合はその新規 Issue

## 完了条件

- [ ] PR タイトルが `[#<issue番号>] <価値を示す短い動詞句>` 形式
- [ ] PR 本文のテンプレ欄がすべて埋まっている
- [ ] CI がすべて green
- [ ] 実験がある場合 HTML レポートへのリンクが本文にある
- [ ] Issue と PR が相互にリンクされている（`Closes #<番号>`）

## 注意点

- **Issue の本文を PR にコピペしない**。Issue は「なぜやるか」、PR は「何をしたか・何を見てほしいか」を書く
- **CI が落ちているのに Ready にしない**。Draft を活用する
- **merge の方針は branch-strategy.md に従う**。squash か rebase かの選択は個人判断で変えない
- **force push はトピックブランチ内でも慎重に**。レビュー中の force push はレビュアーのコメント位置がズレる
- **レビュー指摘を説得で閉じない**。合意できない点は Issue コメントとして分離し、別 Issue に切り出して合意を作る

## PR タイトル例

- ✅ `[#42] 研究者が 100 万人規模の合成人口を 1 時間で生成できるようにする`
- ✅ `[#58] 秘匿性評価の距離定義を 1 枚に集約する`
- ❌ `SA を実装`（何のためか分からない）
- ❌ `Fix bug`（範囲が見えない）

## PR 本文テンプレート（抜粋・全体は `.github/pull_request_template.md`）

```markdown
## 背景
<Issue の価値を 2〜3 行で再掲。ただし Issue のコピペではなく、要点に絞る>

## この変更で提供する価値
<利用者視点で 1 文>

## 変更内容
- <論理単位の変更 1>
- <論理単位の変更 2>

## 影響範囲
- 変更モジュール: ...
- 他モジュールへの影響: ...
- 既存 API の互換性: ...

## テスト
- 追加テスト: N 件
- カバレッジ: ...
- 手動確認: あり/なし、内容

## 実験 / 検証
- 実験 ID: `experiments/<日付>-<slug>`
- 主要結果: ...
- HTML レポート: `experiments/<日付>-<slug>/report.html`

## 残課題
- [ ] #<別 Issue 番号>: ...

## レビュアーに特に見てほしい点
- <設計判断 / 実験の妥当性 / その他>
```

## GitHub Issue / PR に書くべきこと（段階 4 終了時点）

- Issue: PR へのリンクと、段階 3 のレビューサマリが両方ある状態
- PR: 上記テンプレをすべて埋めた状態で Ready になっている
- HTML レポート: PR 本文から 1 クリックで辿れる
