# TDD 運用ルール

本リポジトリでは **テスト駆動開発（TDD; Test-Driven Development）** を基本にします。
ここでは「なぜ TDD か」「どう進めるか」「どこまで厳密にやるか」を定めます。

---

## 1. なぜ TDD か

- **振る舞いを言葉にする**: テストを先に書くと、「何を作るか」を自然言語ではなくコードで宣言することになる。曖昧さが露呈する
- **小さく検証する**: 1 サイクルで変わる範囲が小さい。どこで壊れたかが直接分かる
- **回帰を捕まえる**: 後続 Issue の実装が過去の振る舞いを壊したとき、即座に検知できる
- **実験の妥当性を守る**: 評価指標計算や距離計算のような「正しい答えが別途計算できる」処理は、テストが無いと誤差か仕様か判断できなくなる

研究プロトタイプだからこそ、**計算結果が何によって保証されているか** を記録しておく必要があります。TDD はその記録手段でもあります。

---

## 2. Red / Green / Refactor

1 つの振る舞いは、以下 3 ステップで進めます。

### Red（落ちるテストを書く）

- 期待する振る舞いを 1 つだけ選ぶ
- まだ実装されていない関数 / クラスを使ってテストを書く
- **実行して本当に落ちることを確認** する（importError だけで赤くなっていないか注意）
- この時点でコミットしてよい（`test: ...` から始まるメッセージ）

### Green（最小実装で通す）

- テストを通す最小限のコードだけ書く
- 「ついでの改善」は別サイクルにする
- 実装後に全テストを走らせ、他が壊れていないか確認

### Refactor（整理する）

- Green のままで、命名・重複・責務分割を整える
- テストは変えない（テストを変える場合は Red サイクルに戻る）
- 十分に小さい Refactor なら別コミットにしない判断もあり（ただし Green コミットと混ぜない）

---

## 3. テストの種類と使い分け

| 種類 | 対象 | 使い方 |
|---|---|---|
| 単体テスト | 1 関数・1 クラス | 引数と戻り値の関係、境界値、例外 |
| 結合テスト | 複数モジュールを通すフロー | 設定ファイル読み込み → 生成 → 出力、の一連 |
| 回帰テスト | 過去のバグ再現ケース | バグ修正時に必ず追加する。Issue 番号をコメントで添える |
| 性質ベーステスト | 入力空間が広い関数 | `hypothesis` などで性質（可換性・保存性など）を確認 |
| スナップショットテスト | 大きな出力（レポート・DataFrame） | 変化があれば人間が差分確認できる形で保存 |

単体テストが骨格、結合テストが保険、回帰テストが記録、というイメージで使い分けます。

---

## 4. どこに置くか

```
tests/
  unit/
    test_<module>.py
  integration/
    test_<flow>.py
  regression/
    test_issue_<番号>_<slug>.py
  fixtures/
    <共通の入力データ>
```

- 実験スクリプト（`experiments/` 配下）に対しては、**別枠のテスト** は要求しません（`experiments/` 自体の再現性ルールで代替）
- 本体コード（`src/` / `synthpop_jp/`）には必ず対応テストが存在すること

---

## 5. 実験コードでの TDD の扱い

探索的実験（例: SA のパラメータ探索、評価指標の可視化）では、厳密な TDD を適用すると手が止まります。代わりに以下のように扱います。

- **実験コードそのもの** は、本体コード（`src/`）を呼び出す形にし、本体コードのテストで妥当性を保証する
- 実験コード固有のロジック（前処理・集計）は、**後からでもよいので** `tests/unit/` にテストを足す
- 「手で結果を見て判断」する部分があってよいが、そこは `experiments/<...>/report.md` に言葉で記録する

原則:

> **本体コードは TDD、実験コードは再現性で守る。**

---

## 6. TDD を守れない場面の扱い

以下のような場面では、TDD の厳密適用を緩めてよい（ただし Issue に理由を記録する）:

- 可視化のパラメータ調整（先に画像を見たい）
- 外部 API 呼び出しのモック構築前
- 新しいライブラリの API を手で試す段階

これらは **探索** と明記し、確定した振る舞いだけを後追いでテストに昇格させます。探索段階のコードを本体コードに混ぜないこと。

---

## 7. コマンド

```bash
# 全テスト
uv run pytest

# 変更に影響するテストだけ（コミット前の高速確認）
uv run pytest --lf           # 直近で落ちたものだけ再実行
uv run pytest -x             # 最初の失敗で停止

# カバレッジ
uv run pytest --cov=src --cov-report=term-missing

# 回帰テストだけ走らせる
uv run pytest tests/regression
```

---

## 8. チェックリスト

Issue 完了前に以下を満たしていること:

- [ ] 計画で挙げたテスト観点が、テストとして実在する
- [ ] 追加・変更した公開関数にテストがある
- [ ] 過去のバグ修正があれば回帰テストが追加されている
- [ ] 全テストが green
- [ ] カバレッジの抜けに意図があり、説明できる

---

## 9. pydantic ValidationError を引き出すテストの書き方

pydantic v2 のモデルは `Literal[...]` などで引数型を絞っていることが多い。
**不正な値を意図的に渡して `ValidationError` を引き出すテスト**では、直接呼び出しだと pyright strict が止めます。

### アンチパターン（pyright 落ちる）

```python
def test_invalid_sex_rejected(self) -> None:
    with pytest.raises(ValidationError):
        DemographicByAgeSexRow(age=30, sex="X", count=100)  # "X" は Literal["M","F"] にない
```

`reportArgumentType` で pyright が落ちます（PR #17 で実際に発生）。

### 正しいパターン

```python
def test_invalid_sex_rejected(self) -> None:
    with pytest.raises(ValidationError):
        DemographicByAgeSexRow.model_validate({"age": 30, "sex": "X", "count": 100})
```

`model_validate(dict)` 経由にすることで、pydantic 側のランタイムバリデーションを正規ルートで引き出せます。
これはローダが CSV の 1 行を処理するパスと同じため、テストの意図にも忠実です。

### 参考

- 現行実装例: `tests/io/test_loaders.py` の `TestDemographicByAgeSexRowSchema`
- 関連: PR #17 で pyright strict 対応として model_validate に統一

---

## 10. テストから repo root を参照する時のパス解決

回帰テストなどで `scripts/` や `data/` を参照したくなったとき、`Path(__file__).parents[N]` の **固定 index は使わない**。

### アンチパターン（worktree の有無で壊れる）

```python
_REPO_ROOT = Path(__file__).parents[4]   # worktree だと 4、CI の checkout だと 3
```

worktree 下では `gitworktree/feature-xxx/tests/regression/test_foo.py` なので `parents[4]` が repo root。
一方 CI の checkout では `<repo>/tests/regression/test_foo.py` なので `parents[3]` が repo root。
固定 index にすると片方で絶対に壊れます（PR #18 で実際に発生）。

### 正しいパターン

```python
def _find_repo_root() -> Path:
    """pyproject.toml を含む最近接の祖先を repo root とみなす."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError(f"pyproject.toml が {here} から辿れない階層に見つからない")


_REPO_ROOT = _find_repo_root()
_GENERATE_SCRIPT = _REPO_ROOT / "scripts" / "generate_sample_case.py"
```

マーカーファイル（`pyproject.toml`）を探索するので、worktree の階層数に依存しません。

### 参考

- 現行実装例: `tests/regression/test_determinism.py` の `_find_repo_root`
- 関連: PR #18 で CI 専用の失敗として修正
