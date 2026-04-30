# 計画: Issue #98 — Gower 距離 (`domain/distance.py`)

対象 Issue: #98
計画作成日: 2026-04-30
担当: Claude (autonomous)

---

## 1. 再確認: 成功条件

| 成功条件 | 担保方法 |
|---|---|
| `synthpop_jp.domain.distance` モジュール新設 | `src/synthpop_jp/domain/distance.py` |
| Gower 距離（数値: range 正規化 L1、カテゴリ: 一致 0/1）の純関数実装 | `gower_distance(x, y, ...)` 関数 |
| 既知の小データで bitwise 一致するユニットテスト | 手計算 fixture |
| N×M レコード対の距離行列 batch API | `gower_distance_matrix(...)` |
| N=1,000 × M=1,000 の所要時間が 10 秒以内 | smoke ベンチ |

## 2. 設計方針

### 2.1 距離定義（Gower 1971）

レコード `i` と `j` の距離:

```
d(i, j) = (1 / p) * Σ_k w_k * d_k(i, j)
```

- `p`: 属性数
- `w_k`: 属性 `k` の重み（既定 1.0）
- `d_k(i, j)`:
  - 数値属性: `|x_i - x_j| / range(x)`、ただし range が 0 なら 0
  - カテゴリ属性: `0` if `x_i == x_j` else `1`

### 2.2 API

```python
def gower_distance(
    x: ArrayLike,        # shape=(p,) 1 レコード
    y: ArrayLike,        # shape=(p,) 1 レコード
    *,
    is_numeric: Sequence[bool],   # 各属性が数値かカテゴリか
    ranges: Sequence[float],      # 数値属性の range（事前計算）
) -> float

def gower_distance_matrix(
    x: ArrayLike,        # shape=(N, p)
    y: ArrayLike,        # shape=(M, p)
    *,
    is_numeric: Sequence[bool],
    ranges: Sequence[float] | None = None,  # None なら x∪y から計算
) -> np.ndarray         # shape=(N, M)
```

vectorize：numpy operations で N×M を 2 重ループなしに計算する。

### 2.3 PopulationArrays との連携

便宜関数として `gower_distance_matrix_for_pop(pop_a, pop_b)` を追加。固定属性 `(age=numeric, sex/role/family_type=categorical)` で行列を返す。

## 3. 実装方針

### 追加するファイル

- `src/synthpop_jp/domain/distance.py` — Gower 距離本体
- `tests/domain/test_distance.py` — ユニットテスト

### 変更するファイル

なし（新規モジュールのみ）

### 着手順

1. **Cycle 1**: `gower_distance` の RED テスト（手計算 4 件）→ 実装
2. **Cycle 2**: `gower_distance_matrix` の RED テスト（小データ）→ 実装（vectorize）
3. **Cycle 3**: `gower_distance_matrix_for_pop` の便宜関数 → 実装
4. **Cycle 4**: ベンチ smoke（N=M=100 で finite かつ 1 秒以内 → 1000×1000 は別途確認）

## 4. テスト観点

### 単体テスト

- [ ] 同一レコードの距離 = 0
- [ ] 数値属性のみ: range 正規化 L1 と一致
- [ ] カテゴリ属性のみ: ハミング率と一致
- [ ] 混在: 重み付き平均
- [ ] 対称性 d(x, y) == d(y, x)
- [ ] range=0 で divisor by zero にならない
- [ ] `gower_distance_matrix` が 2 重ループ実装と数値一致
- [ ] N=0 または M=0 で空行列を返す

### 結合テスト

該当なし（distance.py 単体）

### 回帰テスト

既存 627 テスト維持

## 5. 実験計画

該当なし。

## 6. リスクと代替案

### 失敗モード

- **range=0（属性が定数）**: 0 で division by zero。`np.where` で処理。
- **メモリ**: N=10,000 × M=10,000 で float64 行列は 800MB。N=1,000 までは安全
- **vectorize の精度**: 1e-9 以内の許容差を assert で確認

### Plan B

vectorize でメモリ不足なら chunk 化（行列を 1000 行ずつ計算）— 別 Issue で対応。

## 7. 作成した worktree / branch

- worktree: `gitworktree/feature-98-gower-distance/`
- branch: `feature/98-gower-distance`
- 派生元: `origin/develop` @ `7cff646`（#96 マージ後）

## 8. レビュー段階で確認したい論点

- range の事前計算 vs オンザフライ計算の判断
- 数値属性が int / float の場合の挙動
- カテゴリ属性で型が異なる場合の比較規則

---

## チェックリスト

- [x] 成功条件を再確認した
- [x] 設計方針・実装方針・テスト観点・リスクの 4 項目が揃っている
- [x] 実験は伴わない
- [x] worktree / branch が作成済み
- [ ] PR 本文から Issue にリンク
