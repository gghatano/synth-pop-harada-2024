# Data Contract（入力 CSV のスキーマ契約）

**ステータス: v0.1.0（Phase 1 で肉付け済み）**

本ドキュメントは `synthpop-jp` が受け取る全 CSV ファイルのスキーマ契約を一元化する。`docs/spec/spec.md` §7 から本書に委譲されている。

## 1. 対象範囲と責務

**何をここで決めるか**: 入力 CSV の列名・型・単位・欠損規則・値域・相互整合制約、pydantic v2 バリデーションのエラー規約、SemVer による契約バージョン管理。

**ここで決めないこと**: 評価指標の距離定義（`docs/spec/metrics.md`）、実験 protocol（`docs/experiment_plan.md`）、データ出所・倫理（`docs/assumptions.md`）。

本書が「契約」として固まることで、ローダ実装（`io/loaders.py`）とダミー生成器（`scripts/generate_sample_case.py`）と e-Stat adapter（`data/templates/estat/`）が分岐しなくなる。

---

## 2. ファイル別スキーマ

### 2.1 family_type_counts.csv（必須）

家族類型別の世帯数。`spec.md` §8.1 で定義された 9 種類を含む。

pydantic モデル: `FamilyTypeCountRow`（`src/synthpop_jp/io/schemas.py`）

| 列名 | dtype | 単位 | 値域 | null 可 | 説明 |
|---|---|---|---|---|---|
| `family_type` | str | - | 任意（§8.1 の 9 種を推奨） | 不可 | 家族類型名 |
| `count` | int | 世帯 | 0 以上 | 不可 | 世帯数 |

**サンプル（3 行）**

```csv
family_type,count
single,15
couple,20
couple_and_children,30
```

---

### 2.2 children_count_dist.csv（必須）

家族類型グループ別・子ども人数の分布。「子どもがいる家族類型」と「子どもがいない家族類型」で別々のグループを持つ。

pydantic モデル: `ChildrenCountDistRow`

| 列名 | dtype | 単位 | 値域 | null 可 | 説明 |
|---|---|---|---|---|---|
| `family_type_group` | str | - | `configs/family_type_mapping.yaml` の values | 不可 | 家族類型グループ名 |
| `n_children` | int | 人 | 0 以上 | 不可 | 子ども人数 |
| `rate` | float | - | 0.0〜1.0 | 不可 | グループ内でその人数の割合 |

**相互整合制約**: `(family_type_group, n_children)` の組み合わせが重複してはならない。

**サンプル（3 行）**

```csv
family_type_group,n_children,rate
with_children,1,0.50
with_children,2,0.35
with_children,3,0.15
```

---

### 2.3 demographic_by_age_sex.csv（必須）

年齢・性別別の人口分布（人口ピラミッド）。

pydantic モデル: `DemographicByAgeSexRow`

| 列名 | dtype | 単位 | 値域 | null 可 | 説明 |
|---|---|---|---|---|---|
| `age` | int | 歳 | 0〜120 | 不可 | 年齢（歳単位） |
| `sex` | str | - | `"M"` または `"F"` | 不可 | 性別（M=男性, F=女性） |
| `count` | int | 人 | 0 以上 | 不可 | 人口 |

**サンプル（3 行）**

```csv
age,sex,count
30,M,100
30,F,95
35,M,90
```

---

### 2.4 age_diff_parent_child.csv（必須）

親子年齢差の分布。父・母それぞれについて記録する。

pydantic モデル: `AgeDiffParentChildRow`

| 列名 | dtype | 単位 | 値域 | null 可 | 説明 |
|---|---|---|---|---|---|
| `role` | str | - | `"father"` または `"mother"` | 不可 | 親の役割 |
| `diff_min` | int | 歳 | 任意整数 | 不可 | 年齢差の下限（含む） |
| `diff_max` | int | 歳 | `diff_min` より大 | 不可 | 年齢差の上限（含まない） |
| `count` | int | 件 | 0 以上 | 不可 | 観測数 |

**年齢差の定義**: `diff = parent_age - child_age`（親の年齢 − 子の年齢）。親が年上なので通常は正値。

**半開区間規約**: `[diff_min, diff_max)` の左閉右開で表現する。`diff_min < diff_max` であること。

**サンプル（3 行）**

```csv
role,diff_min,diff_max,count
father,20,25,30
father,25,30,40
mother,18,23,25
```

---

### 2.5 age_diff_couple.csv（必須）

夫婦年齢差の分布。

pydantic モデル: `AgeDiffCoupleRow`

| 列名 | dtype | 単位 | 値域 | null 可 | 説明 |
|---|---|---|---|---|---|
| `diff_min` | int | 歳 | 任意整数 | 不可 | 年齢差の下限（含む） |
| `diff_max` | int | 歳 | `diff_min` より大 | 不可 | 年齢差の上限（含まない） |
| `count` | int | 件 | 0 以上 | 不可 | 観測数 |

**couple_diff の符号規則（§4 で確定）**: `couple_diff = husband_age - wife_age`（夫の年齢 − 妻の年齢）。夫が年上なら正、妻が年上なら負。

**半開区間規約**: `[diff_min, diff_max)` の左閉右開。`diff_min < diff_max` であること。

**サンプル（3 行）**

```csv
diff_min,diff_max,count
-5,0,10
0,5,30
5,10,20
```

---

### 2.6 demographic_by_family_type_role.csv（任意）

家族類型 × 役割 × 性別 × 年齢別の人口。SA 実行における年齢割当の精度向上に使う。

pydantic モデル: `DemographicByFamilyTypeRoleRow`

| 列名 | dtype | 単位 | 値域 | null 可 | 説明 |
|---|---|---|---|---|---|
| `family_type` | str | - | 任意（§8.1 の 9 種を推奨） | 不可 | 家族類型名 |
| `role` | str | - | 任意（§8.2 の例を参照） | 不可 | 役割 |
| `sex` | str | - | `"M"` または `"F"` | 不可 | 性別 |
| `age` | int | 歳 | 0〜120 | 不可 | 年齢 |
| `count` | int | 人 | 0 以上 | 不可 | 人口 |

**業務ルールの注意**: 値の意味（役割ごとの年齢範囲の適切性など）は Phase 2 以降で定義する。本 Phase では型と値域のみ検証する。

---

### 2.7 household_size_by_family_type.csv（任意）

家族類型別の世帯人数分布。

pydantic モデル: `HouseholdSizeByFamilyTypeRow`

| 列名 | dtype | 単位 | 値域 | null 可 | 説明 |
|---|---|---|---|---|---|
| `family_type` | str | - | 任意（§8.1 の 9 種を推奨） | 不可 | 家族類型名 |
| `household_size` | int | 人 | 1 以上 | 不可 | 世帯人数 |
| `count` | int | 世帯 | 0 以上 | 不可 | 世帯数 |

---

## 3. 半開区間文字列と diff_min/diff_max の規約

**確定方針（Phase 1）**: `diff_min: int` / `diff_max: int` の **2 列表現**（左閉右開: `diff_min <= x < diff_max`）を採用する。

- 整数型で型安全に扱えること、pydantic の `ge/lt` バリデーションと親和性が高いことが採用理由。
- `"[-5,-3)"` 形式の文字列は受け付けない。前処理スクリプトで変換すること。

---

## 4. `couple_diff` の符号規則

**確定（Phase 1 / Issue #12 で確定）**:

- **`couple_diff = husband_age - wife_age`**（夫の年齢 − 妻の年齢）に統一する
- 夫が年上なら正、妻が年上なら負
- 入力 CSV 側が逆符号の場合はローダに渡す前に前処理スクリプトで反転すること
- ローダ（`load_age_diff_couple`）は符号反転を行わない
- `DATASET.md` に出典別の符号慣習を記録すること（e-Stat データ利用時に要確認）

この規則は `src/synthpop_jp/io/schemas.py` の `AgeDiffCoupleRow` と `src/synthpop_jp/io/loaders.py` の `load_age_diff_couple` ドキュメントにも明記されている。

---

## 5. `family_type` ↔ `family_type_group` マッピング

**初版配布（Phase 1）**: `configs/family_type_mapping.yaml` に 9 種類の family_type → 3 グループへのマッピングを定義する。

```yaml
single: single
couple: without_children
couple_and_children: with_children
...
```

**グループの定義**:

| family_type_group | 意味 | 含む family_type（例） |
|---|---|---|
| `with_children` | 子どもがいる世帯 | `couple_and_children`, `father_and_children` など |
| `without_children` | 子どもがいない（単身以外） | `couple`, `couple_and_parents` など |
| `single` | 単身世帯 | `single` |

**参照方法**: `load_family_type_mapping(path)` で `dict[str, str]` として読み込む。Phase 3 以降は `registry.register_family_type` に統合する。

---

## 6. pydantic v2 `TypeAdapter` エラー規約

**実装済み（Phase 1）**:

- ローダは `pandas.read_csv` → `to_dict(orient="records")` → 行ループで `Model.model_validate(record)` を実行する
- 失敗した行の **0-indexed 行番号**（pandas の行番号と一致）を `CsvValidationError` に含める
- エラーメッセージ形式: `"row {N}: {field}: {message}"` （N は 0-indexed）
- `CsvValidationError` は `src/synthpop_jp/io/loaders.py` に定義される
- CLI の `synthpop-jp validate-config` は同じフォーマッタを使う（Phase 2 で実装）

**エラーの例**:

```
row 3: count: Input should be greater than or equal to 0
row 7: sex: Input should be 'M' or 'F'
```

---

## 7. 変更履歴（SemVer）

本契約は SemVer で版管理する。

- 破壊的変更（列名変更・必須列追加など）は **MAJOR**
- 新しい任意列の追加は **MINOR**
- 説明やエラーメッセージの改善は **PATCH**

変更は本書末尾の「履歴」セクションに日付付きで追記する。v0.x の間は破壊的変更を許容する旨を `CHANGELOG.md` と整合させる。

---

## 8. 履歴

- 2026-04-23: v0.0.1 骨子作成（Phase 0）
- 2026-04-24: v0.1.0 Phase 1 で全 CSV 5 種 + 任意 2 種の表を肉付け、`couple_diff` 符号規則を確定、`diff_min/diff_max` の 2 列形式を採用（Issue #12）
