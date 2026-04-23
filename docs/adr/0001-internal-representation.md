# ADR-0001: 内部表現は NumPy 並列配列 + 差分更新

- **Status**: Accepted
- **Date**: 2026-04-23

## Context

`docs/spec/spec.md` 旧版の §8 データモデルは `Household.members: list[Person]` という OOP 表現を採用しており、§11.4 の目的関数はその上で `observed[s, j]` を都度集計する形を想定していた。一方、§12 の SA は `max_iters: 200000` を想定し、§15.1 の実験では `evals_per_agent ∈ {1000, ..., 16000}` を回す。

この構造のまま進めると、1 遷移ごとに `list[Household]` を全走査して集計し直す必要があり、N = 数千世帯 × 20 万反復で**非現実的な速度**になる。`Person` を pydantic モデルにするとさらに数倍遅くなる。§11.5 の親子年齢・夫婦年齢制約判定も世帯内ペアを都度走査すると重い。

レビュー `docs/reviews/review-python.md` 指摘 1 は、Phase 1 着手前に SA 内部表現を「NumPy 並列配列 + 差分更新」に固定することを強く求めている。これを先送りすると Phase 2 で必ず大規模な手戻りが発生する。

## Decision

**I/O・外部 API** と **SA 内部表現** を二層に分離する。

### I/O・外部 API 層

- pydantic v2 `BaseModel`（バリデーション目的のみ）
- `Household`, `Person` は §8 の外部データモデルとして残す
- CSV ローダ・`writers.py`・CLI 境界・config でのみ使う

### SA 内部表現層（`optimize/state.py`）

```python
@dataclass
class PopulationArrays:
    age: np.ndarray           # int16, shape=(n_persons,)
    sex: np.ndarray           # int8  (0=M, 1=F)
    role: np.ndarray          # int8  (enum)
    household_id: np.ndarray  # int32
    family_type: np.ndarray   # int8  (enum, person-broadcast)
```

- NumPy 並列配列（Structure of Arrays）で固定
- dtype を明示（int16 / int8 / int32）してメモリ局所性を最大化
- person-broadcast された `family_type` を冗長に持ち、family type ごとの集計を vectorize できるようにする

### 差分更新版目的関数（`optimize/objective.py`）

- `observed[s, j]` を保持変数として持ち、遷移前後で影響を受けるビンのみ `+1 / -1` する
- `abs(observed - target)` の総和 `score` も差分で反映（1 遷移 O(1)）
- `ObjectiveState` クラスが `propose / apply / revert` の 3 メソッド API で SA の全遷移を扱う
- この API は `domain/protocols.py` の `Transition` Protocol と整合する

### ドメイン層 ↔ 並列配列 の変換

- `optimize/state.py` に `from_households(list[Household]) -> PopulationArrays` と `to_households(...) -> list[Household]`
- I/O 境界でのみ変換し、SA 内部では変換しない

## Consequences

### 肯定的な結果

- **性能**: 1 遷移 O(1) の差分更新が成立し、20 万反復が 30 秒オーダで回る見込み（pytest-benchmark で Phase 2 の Exit 条件として確認する）
- **決定性テスト**: NumPy 配列なので seed 固定で bitwise 一致を assert しやすい
- **property test**: hypothesis で「差分更新と全再計算の結果が一致する」を検証できる
- **メモリ**: dtype を絞った並列配列で N = 10 万人程度まで RAM 内で扱える

### 否定的な結果

- **OOP 的な可読性は下がる**: SA 内部コードで `person.age` ではなく `arrays.age[i]` を読む必要がある
- **I/O 層との往復コスト**: CSV → pydantic → `PopulationArrays` の変換が必要（ただし 1 run に 1 回のみ）
- **遷移実装の認知負荷**: `propose / apply / revert` の対応関係を正しく保つ property test が必須

### 将来の差分プライバシー (DP) 拡張

- 並列配列はそのまま、目的関数側を noisy target を受けられるよう `Distribution` Protocol で抽象化する（`domain/protocols.py`）
- 本 ADR の決定は DP 拡張と衝突しない

## References

- レビュー指摘の逆参照: `docs/reviews/review-python.md` 指摘 1（最重要）、指摘 5（Protocol 切り出し）、追加タスク B（差分更新 PoC）、追加タスク D（hypothesis property test）
- `docs/reviews/action-plan.md` §1.2「内部表現 vs 拡張性」
- `docs/spec/spec.md` §9（ディレクトリ）、§12.1（SA 共通）
- 関連 ADR: なし（本 ADR が初）
