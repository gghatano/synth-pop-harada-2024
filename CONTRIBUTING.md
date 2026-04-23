# Contributing to synthpop-jp

`synthpop-jp` への貢献を歓迎します。本ドキュメントは、コード・ドキュメント・評価器プラグインを送る際の手順と規約をまとめたものです。

本プロジェクトの根本ルールは `CLAUDE.md` に集約されています。本書と食い違う場合は `CLAUDE.md` が優先します。

---

## 1. はじめに

まずは `CODE_OF_CONDUCT.md` に目を通してください。すべての参加者が安心して貢献できる場を維持することを最優先します。

次に、何を作っているプロジェクトかを `README.md` で把握してください。本リポジトリは **Murata 2017 の合成人口生成手法の Python 再実装** と **Harada 2024 の評価軸（ARD 等）** を 1 つのツールキットに載せる研究用 OSS です。

---

## 2. 開発環境のセットアップ

前提: Python 3.11 以上、`uv`（[公式インストール手順](https://docs.astral.sh/uv/)）。

```bash
# 1. clone（フォーク経由を推奨）
git clone https://github.com/<your-account>/synth-pop-harada-2024.git
cd synth-pop-harada-2024

# 2. 依存関係を `uv.lock` に従って同期（完全再現）
uv sync --frozen

# 3. pre-commit フックを有効化（ruff / ruff-format / pyright をローカルでも実行）
uv run pre-commit install

# 4. テストが全部通ることを確認
uv run pytest
```

`uv sync --frozen` で失敗する場合は `uv.lock` が古い可能性があります。メンテナに Issue で連絡してください（自分で `uv lock` を回さないでください。`uv.lock` は Phase 0 task-004 で確立したコミット対象です）。

---

## 3. Issue 駆動開発フロー

本リポジトリでは **コードを書く前に必ず Issue を立てます**。Claude Code を使っている場合は `.claude/skills/` の 5 段階 skill を順に呼び出します（`CLAUDE.md` §3 参照）。

| # | 段階 | skill | 主な出力 |
|---|---|---|---|
| 0 | Issue 作成 | `0_issue_create` | 価値起点の Issue 本文 |
| 1 | 計画 | `1_issue_plan` | 実装前の設計・テスト・実験計画 |
| 2 | 実装 | `2_issue_impl` | TDD コード + テスト |
| 3 | 自己レビュー | `3_review_and_refactor` | レビューサマリ、リファクタ差分 |
| 4 | PR 作成 | `4_create_pr` | `develop` 向け PR |

段階を飛ばさないでください。詳細は `docs/rules/issue-driven-development.md` を参照。

---

## 4. ブランチと Worktree

### 4.1 ブランチ戦略

- 開発の基点は `develop` ブランチ（`main` は安定版）
- 作業ブランチ名は `feature/<issue番号>-<keyword>` 形式（例: `feature/42-add-sa-core`）
- 詳細は `docs/rules/branch-strategy.md`

### 4.2 Worktree 配置（必須）

本リポジトリでは `git worktree` を使った並行開発を前提としています。

- worktree の配置: `<repo_root>/gitworktree/feature-<issue番号>-<キーワード>`
- worktree 名 = ブランチ名（スラッシュはハイフンに変換、例: `feature/42-add-auth` → `feature-42-add-auth`）
- **リポジトリ直下（`develop` / `main`）では直接開発しない**

```bash
git fetch origin
git worktree add -b feature/42-add-sa-core gitworktree/feature-42-add-sa-core origin/develop
cd gitworktree/feature-42-add-sa-core
```

詳細は `docs/rules/git-worktree.md` と `CLAUDE.md` §4.2。

---

## 5. コミットメッセージと PR

### 5.1 コミットメッセージ規約

作業中のコミット単位は自由（細かく切って構いません）。ただし、**PR マージ時は squash merge** を既定とし、その際のコミットメッセージは以下の形式に整形します。

```
[#<issue番号>] <価値を示す短い動詞句>

<PR 本文の「背景」「提供する価値」を数行で要約>

Closes #<issue番号>
```

詳細は `docs/rules/branch-strategy.md` §5。

### 5.2 PR のチェックリスト

PR を出す前に:

- [ ] `origin/develop` を取り込み、コンフリクトなし（`git rebase origin/develop`）
- [ ] rebase 後に `uv run pytest` が緑
- [ ] `uv run ruff check` と `uv run pyright` が緑
- [ ] CI が緑（全ジョブ）
- [ ] 必要に応じて ADR を追加している（仕様の不可逆な意思決定を伴う場合）
- [ ] `CHANGELOG.md` の `[Unreleased]` セクションを更新している
- [ ] 関連 Issue を `Closes #<n>` で引用している

---

## 6. テスト駆動開発 (TDD)

新しい振る舞いには、まず **落ちるテスト** を書いてから実装します（`CLAUDE.md` §4.1）。

Red → Green → Refactor の 3 ステップを守ってください。探索的な実験コードは `experiments/` 配下に分離し、そちらは厳密な TDD を要求しません（代わりに再現性ルールが適用されます。`docs/rules/experiment-management.md` 参照）。

---

## 7. 拡張ポイント — プラグインを足す

`synthpop-jp` は 3 種類の拡張ポイントを公開予定です。いずれも Phase 1〜3.5 で API が確定するため、この節の例は暫定です（**Phase 1 完成後に `register_family_type` を追記**、**Phase 3.5 完成後に `Evaluator` 例を追記** する前提）。

### 7.1 新しい `family_type` を足す（10 行例・暫定）

```python
# my_plugin/families.py
# TODO: 本 API は Phase 1 (task-007) で確定予定。以下はシグネチャのみを示す暫定例。
from synthpop_jp.domain import register_family_type, FamilyTypeTemplate

register_family_type(
    name="single_parent_with_grandparent",
    template=FamilyTypeTemplate(
        roles=["parent", "child", "grandparent"],
        constraints={"min_size": 3, "max_size": 6},
    ),
)
```

### 7.2 新しい `Evaluator` を足す（20 行例・暫定）

`pyproject.toml` の entry_points 経由で外部パッケージからも登録できる予定です。

```python
# my_plugin/evaluators.py
# TODO: 本 API は Phase 3.5 で確定予定。以下はシグネチャのみを示す暫定例。
from synthpop_jp.evaluate import Evaluator, EvaluatorResult

class MyCustomMetric(Evaluator):
    name = "my_custom_metric"

    def evaluate(self, synthetic, reference) -> EvaluatorResult:
        # 実個票と合成人口の距離などを返す
        score = ...  # 具体的な計算
        return EvaluatorResult(score=score, details={"n": len(synthetic)})
```

```toml
# my_plugin/pyproject.toml
[project.entry-points."synthpop_jp.evaluators"]
my_custom_metric = "my_plugin.evaluators:MyCustomMetric"
```

インストールすれば `synthpop-jp evaluate --metric my_custom_metric ...` で呼べるようになる予定です。

### 7.3 新しい遷移 (transition) を足す

遷移関数（age-change / age-swap 以外）のレジストリ API は Phase 2〜3 で公開します。API 確定後に本節を更新します。

---

## 8. ドキュメント規約

- 文章スタイルは `docs/rules/documentation-style.md` と `CLAUDE.md` §4.5 を参照
- **非技術者にも読める形で書く** ことを最優先
- 1 文を長くしない。専門用語には一言の補足を添える
- 「何が変わるか」「なぜ必要か」を先に書く。実装詳細はその後

---

## 9. 実験の再現性

実験コードを追加する場合、seed・データ・設定・コミット SHA を必ず記録してください。実験レポートは `experiments/<日付>-<slug>/report.md` に Markdown で作成し、HTML 化して保存します。詳細は `docs/rules/experiment-management.md`。

---

## 10. 困ったら

- GitHub Issue（Discussions が有効ならそちらへ）
- メール: `adad.0405@gmail.com`

雑な質問でも構いません。「自分の統計表で動かない」「評価指標を足したいが API が分からない」などは特に歓迎します。
