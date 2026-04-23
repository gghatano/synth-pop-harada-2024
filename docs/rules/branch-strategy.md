# ブランチ戦略

本リポジトリは **`develop` を開発の基点、`main` を安定版** とする二本立てを採用します。
作業ブランチは `develop` から派生させ、PR を `develop` 向けに出します。

---

## 1. 主要ブランチ

| ブランチ | 役割 | 直接 push |
|---|---|---|
| `main` | 安定版（リリース済み・タグ打ち対象） | 不可 |
| `develop` | 開発の基点。全 feature がここに集約される | 原則不可（PR 経由） |
| `feature/<issue番号>-<keyword>` | 作業ブランチ | 所有者のみ |

`main` への取り込みは、`develop` での十分な安定化の後、リリース担当者が別途行います（リリースプロセスは本書の対象外）。

---

## 2. ブランチ命名規則

- 形式: `feature/<issue番号>-<keyword>`
- `<keyword>` は 2〜4 語の英小文字ハイフン区切り
- 大文字・日本語・スペースは使わない

### 例

| Issue | ブランチ名 |
|---|---|
| #42 SA コア実装 | `feature/42-add-sa-core` |
| #58 距離定義の集約 | `feature/58-metrics-doc` |
| #112 CAP ベースラインの追加 | `feature/112-privacy-cap-baseline` |
| #203 HTML レポート生成の自動化 | `feature/203-html-report-automation` |

### 機能以外のブランチ種別（必要になった場合のみ）

| 接頭辞 | 用途 |
|---|---|
| `feature/` | 新機能 / 改善 / 実験 |
| `fix/` | バグ修正 |
| `chore/` | 依存更新・リポジトリ整備 |
| `docs/` | ドキュメントのみの変更 |

ただし、原則としてすべて `feature/` で始めて問題ありません。種別を分ける必要が出たときに追加します。

---

## 3. Issue 番号との対応

- 作業は必ず Issue が先にある状態で始める（`0_issue_create` 参照）
- ブランチ名の Issue 番号は、対応 Issue と 1 対 1
- 1 つのブランチで複数 Issue を扱わない（混ざったら分割する）

---

## 4. 作成から PR までの同期ルール

### 作成時

```bash
git fetch origin
git worktree add -b feature/42-add-sa-core gitworktree/feature-42-add-sa-core origin/develop
```

### 作業中に develop が進んだ場合

```bash
cd gitworktree/feature-42-add-sa-core
git fetch origin
git rebase origin/develop
# コンフリクトがあれば解決 → git rebase --continue
uv run pytest    # rebase 後にテストが通ることを確認
```

- **PR を出す前に必ず 1 回は同期する**（CI の無駄な再実行を減らす）
- 長く放置した feature ブランチは develop との乖離が大きくなるので、こまめに rebase

### force push の扱い

- トピックブランチ内での rebase 後に `git push --force-with-lease` は許容
- ただし **レビュー中（レビュアーがコメントを書いた後）** の force push は極力避ける
  - 理由: コメントの行位置がズレ、レビュアーが混乱する
  - 必要な場合は PR コメントで事前に告知する

---

## 5. merge 方針

本リポジトリでは PR merge 時に **squash merge** を既定とします。

| 方針 | 内容 |
|---|---|
| squash merge（既定） | feature ブランチの全コミットを 1 つにまとめて develop に載せる |
| rebase merge | コミット履歴を細かく残したい場合のみ（例: 学習目的の段階的な実装履歴） |
| merge commit | 原則使わない |

### squash merge を既定にする理由

- `develop` の履歴が「1 Issue = 1 コミット」で読みやすい
- 作業中の `wip` 的コミットが履歴に残らない
- 各 PR が revert しやすい

### squash merge 時の commit メッセージ規約

```
[#<issue番号>] <価値を示す短い動詞句>

<PR 本文の「背景」「提供する価値」を数行で要約>

Closes #<issue番号>
```

---

## 6. `develop` / `main` を守る設定

（初期セットアップ時に GitHub 側で設定）

- `main` / `develop` は **保護ブランチ** にする
- `develop` への push は PR 経由のみ、承認 1 名以上、CI green を必須にする
- `main` への push はリリース担当者のみ

---

## 7. チェックリスト

### 作業開始時
- [ ] `develop` から派生した
- [ ] ブランチ名が `feature/<issue番号>-<keyword>` 形式
- [ ] Issue と 1 対 1 で対応している

### PR 作成前
- [ ] `origin/develop` を取り込み、コンフリクトが無い
- [ ] rebase 後に全テスト green
- [ ] コミットメッセージが意味単位で揃っている

### merge 後
- [ ] worktree を削除
- [ ] ローカルの feature ブランチを削除
- [ ] 対応 Issue が close されている
