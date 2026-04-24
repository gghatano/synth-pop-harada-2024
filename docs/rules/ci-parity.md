# CI parity 運用ルール

本リポジトリでは **push 前の手元検査が CI と同一になる** ことを守ります。
「ローカルでは通ったのに CI で落ちる」は可能な限りゼロに近づけます。

---

## 1. なぜ CI parity か

Phase 1 実装で、サブエージェントが `uv run pyright src/` のように **部分検査** で済ませて push し、
CI の `uv run pyright`（引数なし、src+tests 両方を検査）で落ちる事故が PR #17・#18 で連続発生しました。
CI は `.github/workflows/ci.yml` の定義に従い、tests も検査対象に含みます。
部分検査で「0 errors」と言っても、CI で落ちれば意味がありません。

そのため本リポジトリでは、**push 前に以下 4 コマンドを必ず走らせる** ことを運用ルールとします。

---

## 2. push 前に走らせる 4 コマンド

以下の順で実行します。順番は CI と合わせています。

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
```

いずれかが赤なら push しません。

### 各コマンドの意味

| コマンド | 目的 | CI 側 |
|---|---|---|
| `uv run ruff check .` | lint（未使用 import、行長など） | `Ruff check` ステップと同一 |
| `uv run ruff format --check .` | フォーマット統一確認 | `Ruff format --check` ステップと同一 |
| `uv run pyright` | 型検査（strict、src+tests 両方） | `Pyright (strict)` ステップと同一 |
| `uv run pytest` | 全テスト | `Pytest (coverage)` ステップと同一 |

> **重要**: `uv run pyright src/` や `uv run pytest tests/unit/` のように対象を絞って済ませるのは NG です。
> CI は対象を絞らないため、差分が出ます。

---

## 3. よくある落とし穴

### 3.1 pyright strict は tests にも適用される

`pyrightconfig.json` の `include` は `["src", "tests"]` です。
tests 側で意図的に不正な Literal 値を渡すときは、型注釈を通さない書き方にします（`docs/rules/tdd.md` §9 参照）。

### 3.2 テストから repo root を参照するときのパス解決

`Path(__file__).parents[N]` は worktree 利用時と CI チェックアウト時で階層数が異なり、固定 index では壊れます。
`pyproject.toml` を含む最近接の祖先を repo root とみなす探索方式に統一します（`docs/rules/tdd.md` §10 参照）。

### 3.3 `uv run` を省略しない

`ruff check .` / `pytest` を `uv` の外で走らせると、システムの古いバージョンが使われて結果が食い違うことがあります。
**常に `uv run` を前置** してください。

---

## 4. チェックリスト

- [ ] push 前に 4 コマンドを全部走らせた
- [ ] `uv run pyright`（引数なし）で src+tests 両方に 0 errors
- [ ] 「部分検査で済ませた」が無い
- [ ] 失敗した場合は push しない、原因を潰してから再検査

---

## 5. 関連ドキュメント

- `.github/workflows/ci.yml`（CI の実行コマンドの一次情報）
- `pyrightconfig.json`（pyright の検査対象）
- `.claude/skills/2_issue_impl.md` 完了条件
- `docs/rules/tdd.md` §9, §10（テスト書き方の具体）
