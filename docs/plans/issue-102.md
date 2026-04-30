# 計画: Issue #102 — mkdocs サイト v0.2

対象 Issue: #102
計画作成日: 2026-04-30

---

## 1. 再確認: 成功条件と本 PR のスコープ

Issue #102 の成功条件を **MVP** と **stretch** に分解する。本 PR は MVP のみを完了させ、tutorial notebook と GitHub Pages デプロイは別 Issue へ分離する（時間的制約から）。

| 成功条件 | スコープ |
|---|---|
| `mkdocs.yml` と GitHub Pages デプロイの仕組みが整備されている | **MVP**: mkdocs.yml + ローカル build。Pages デプロイは stretch |
| 日本語版 + 英語版が併設（最低 README + how-it-works レベル） | **MVP**: 英語版 README + how-it-works 概要を新設 |
| tutorial notebook 3 本（quickstart / SA / evaluate） | **stretch**: 別 Issue（実行確認に時間が必要） |
| CI で mkdocs build が走る | **MVP**: GitHub Actions に build step 追加 |
| 公開 URL から各ページに到達できる | **stretch**: Pages デプロイ |

## 2. 設計方針

- **テーマ**: Material for MkDocs（広く使われ、検索・多言語をサポート）
- **構造**: `docs/` 直下に既存の `getting-started/` `rules/` `spec/` `reports/` を取り込む
- **多言語**: i18n プラグインは導入せず、`index.md`（日本語）と `index.en.md`（英語）の 2 ファイル併置で済ませる（v0.2 MVP）
- **CI**: `.github/workflows/ci.yml` に `mkdocs build --strict` ジョブを追加（push/PR で実行）
- **Pages デプロイ**: 別 Issue として残す（MVP では `mkdocs build` の成功のみを保証）

## 3. 実装方針

### 追加するファイル

- `mkdocs.yml` — 設定
- `docs/index.md` — トップページ（日本語）
- `docs/index.en.md` — 英語トップ（新規、最小限）
- `docs/guides/how-it-works.en.md` — 英語版手法ガイド（既存日本語版の概要を翻訳）
- `README.en.md` — 既存ファイル更新（mkdocs サイトへの導線追加）
- `Makefile` — `docs` target の置き換え（既存は `exit 1`）

### 変更するファイル

- `.github/workflows/ci.yml` — `mkdocs build --strict` ジョブ追加
- `pyproject.toml` — `[dependency-groups.docs]` に mkdocs 関連を追加

### 着手順

1. mkdocs.yml 作成（既存 docs/ をナビゲーションに取り込む）
2. docs/index.md 作成（日本語）
3. docs/index.en.md 作成（英語）
4. README.en.md 更新（mkdocs サイトへのリンク）
5. Makefile の docs target 実装
6. CI に mkdocs build ジョブ追加
7. ローカルで `mkdocs build --strict` を完走させる

## 4. テスト観点

- [ ] `mkdocs build --strict` が **リンク切れ無し** で完走する
- [ ] `docs/index.md` から既存の `docs/spec/spec.md` などへのリンクが解決する
- [ ] `docs/index.en.md` が独立して読める

## 5. リスクと代替案

### 失敗モード

- **既存 Markdown のリンクが mkdocs strict で切れる**: relative link が build パスで解決しない場合がある。`mkdocs build` で出る warning を 1 つずつ潰す
- **時間切れ**: tutorial notebook と Pages デプロイは別 Issue に分離

### Plan B

mkdocs build が strict mode で完走しない場合は warnings を許容し、修正を別 Issue に切り出す。

## 6. worktree

- worktree: `gitworktree/feature-102-mkdocs-site/`
- branch: `feature/102-mkdocs-site`
- 派生元: `origin/develop` @ `f94d925`
