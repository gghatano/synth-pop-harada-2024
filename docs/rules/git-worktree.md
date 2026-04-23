# git worktree 運用ルール

本リポジトリは **1 Issue = 1 worktree** を基本とします。
「リポジトリ直下で直接編集する」ことを禁止し、作業は必ず worktree 上で行います。

---

## 1. なぜ worktree を使うか

- **複数 Issue を並行できる**: ある Issue の実装中に別 Issue のレビュー依頼が来ても、別ディレクトリで切り替えずに作業できる
- **main / develop を守る**: リポジトリ直下を「見るだけ」に保つことで、誤って develop で直接コミットする事故を防ぐ
- **実験の独立性**: 実験用のブランチと本体改修のブランチが同時に動くとき、`experiments/` ディレクトリの汚染を避けられる
- **Claude Code との相性**: サブエージェントが並行で走るとき、worktree 単位でファイルシステムが分かれているとコンフリクトしない

---

## 2. 配置ルール

```
<repo_root>/
  gitworktree/
    feature-42-add-sa-core/        # Issue #42 用
    feature-58-metrics-doc/        # Issue #58 用
```

- worktree の親ディレクトリは **`<repo_root>/gitworktree/`** に固定
- worktree 名の形式: `feature-<issue番号>-<キーワード>`
  - `<キーワード>` は 2〜4 語程度の英小文字ハイフン区切り
  - 例: `feature-42-add-sa-core`, `feature-112-privacy-cap-baseline`
- **worktree 名とブランチ名は同じ** にする（例: `feature-42-add-sa-core` ⇔ `feature/42-add-sa-core`）
  - ブランチ名にはスラッシュ `feature/...` を使う（branch-strategy.md 参照）
- `gitworktree/` は `.gitignore` に含める（中身はすべて git 管理外扱い）

---

## 3. 作成・削除・一覧

### 作成

```bash
# リポジトリ直下で
git fetch origin
git worktree add -b feature/42-add-sa-core gitworktree/feature-42-add-sa-core origin/develop
cd gitworktree/feature-42-add-sa-core
```

- 必ず `develop` から派生させる（`main` から切らない）
- ブランチがまだ無い場合は `-b` で新規作成
- 既存ブランチを使う場合は `-b` を省略

### 一覧

```bash
git worktree list
```

出力例:
```
/Users/me/works/synth-pop-harada-2024                  abcdef0 [develop]
/Users/me/works/synth-pop-harada-2024/gitworktree/feature-42-add-sa-core  1234567 [feature/42-add-sa-core]
```

### 削除（merge 後）

```bash
cd <repo_root>
git worktree remove gitworktree/feature-42-add-sa-core
git branch -d feature/42-add-sa-core
```

- merge されていないブランチを削除する場合は `-D` だが、**必ず merge / 破棄の意図を確認してから** 使う
- 不要になった worktree を放置するとディスクを食う。PR merge 後は速やかに削除

### 異常時

何らかの理由で worktree ディレクトリを手動削除してしまった場合:

```bash
git worktree prune
```

---

## 4. 複数 Issue を並行で扱うときの注意

- 実験出力は **worktree 内の `experiments/` に置き、ブランチごとに分離** する。他ブランチの実験結果を参照したい場合は該当 worktree に移動するか、HTML レポートを見る
- `uv` / `poetry` の仮想環境は worktree ごとに作成する（`pyproject.toml` が同じでも、依存を書き換える Issue があるため）
- IDE のワークスペース設定（`.vscode/` など）は worktree ごとに別扱い
- 並行作業中に `develop` が進んだ場合、各 worktree で `git rebase origin/develop` をこまめにかける

---

## 5. よくある失敗とその回避

| 失敗 | 回避策 |
|---|---|
| リポジトリ直下で直接編集してしまった | 作業を stash し、worktree を作ってから pop する |
| worktree を作らず feature ブランチを repo 直下で切った | `git worktree add` に切り替える。既存ブランチも指定可能 |
| 他 Issue の worktree で間違えて編集した | `git worktree list` と `pwd` で作業場所を確認する習慣をつける |
| `gitworktree/` を誤ってコミットした | `.gitignore` を確認。revert してから ignore を追加 |

---

## 6. チェックリスト

新しい Issue に着手する直前に以下を確認:

- [ ] リポジトリ直下にいない（`pwd` で確認）
- [ ] 新しい worktree を作った（`git worktree list` に出る）
- [ ] worktree 名とブランチ名の命名規則が一致している
- [ ] `develop` から派生している
- [ ] `gitworktree/` が `.gitignore` に入っている（リポジトリ初期化直後の場合のみ確認）
