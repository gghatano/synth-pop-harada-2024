# Data Contract（入力 CSV のスキーマ契約）

**ステータス: 骨子（Phase 1 で肉付け）**

本ドキュメントは `synthpop-jp` が受け取る全 CSV ファイルのスキーマ契約を一元化する。`docs/spec/spec.md` §7 から本書に委譲されている。

## 1. 対象範囲と責務

**何をここで決めるか**: 入力 CSV の列名・型・単位・欠損規則・値域・相互整合制約、pydantic v2 バリデーションのエラー規約、SemVer による契約バージョン管理。

**ここで決めないこと**: 評価指標の距離定義（`docs/spec/metrics.md`）、実験 protocol（`docs/experiment_plan.md`）、データ出所・倫理（`docs/assumptions.md`）。

本書が「契約」として固まることで、ローダ実装（`io/loaders.py`）とダミー生成器（`scripts/generate_sample_case.py`）と e-Stat adapter（`data/templates/estat/`）が分岐しなくなる。

## 2. ファイル別スキーマ

Phase 1 で `spec.md` §7.1 の全 CSV を列・型・単位・欠損規則で再記述する。各ファイルについて次のテーブルを埋める。

- ファイル名
- 必須/任意
- 列名 / dtype / 単位 / 値域 / null 可否 / 説明
- pydantic v2 モデル名（`FamilyTypeCountRow` など）
- サンプル（5 行）

対象ファイル:

- `family_type_counts.csv`
- `children_count_dist.csv`
- `demographic_by_age_sex.csv`
- `age_diff_parent_child.csv`
- `age_diff_couple.csv`
- `demographic_by_family_type_role.csv`（任意）
- `household_size_by_family_type.csv`（任意）

**Phase 1 で埋める。**

## 3. 半開区間文字列と diff_min/diff_max の規約

- `diff_bin` は **半開区間の文字列** `"[-5,-3)"` 形式で表現する（左閉右開）
- もしくは `diff_min:int, diff_max:int` の 2 列表現（左閉右開で `diff_min <= x < diff_max`）
- 前者を採用した場合は `pandas.Interval` にパースする
- ローダは両形式を受け付けて内部では後者に正規化する

**Phase 1 で最終方針確定。**

## 4. `couple_diff` の符号規則

- **`couple_diff = husband_age - wife_age`** に統一する
- 夫が年上なら正、妻が年上なら負
- 入力 CSV 側が逆符号の場合はローダで反転して正規化する
- `DATASET.md` に出典別の符号慣習を記録する

## 5. `family_type` ↔ `family_type_group` マッピング

- 9 種類の `family_type`（`spec.md` §8.1）から粗い `family_type_group`（例: `with_children` / `without_children` 等）へのマッピング
- yaml で配布: `data/mappings/family_type_group.yaml`
- `registry.register_family_type(name, template)` で外部拡張に開く

**Phase 1 で yaml の初版を配布。**

## 6. pydantic v2 `TypeAdapter` エラー規約

- ローダは `TypeAdapter(list[FamilyTypeCountRow])` で行単位バリデーション
- 失敗時は `rich.console.Console` で **行番号付きエラー** を整形出力
- `errors()` の loc は `(row_index, field_name)` で返す
- CLI の `synthpop-jp validate-config` は同じフォーマッタを使う

**Phase 1 で実装、Phase 0 では規約のみ。**

## 7. 変更履歴（SemVer）

- 本契約は SemVer で版管理する
- 破壊的変更（列名変更・必須列追加など）は **MAJOR**、新しい任意列の追加は **MINOR**、説明やエラーメッセージの改善は **PATCH**
- 変更は本書末尾の「履歴」セクションに日付付きで追記
- v0.x の間は破壊的変更を許容する旨を `CHANGELOG.md` と整合させる

## 8. 履歴

- 2026-04-23: v0.0.1 骨子作成（Phase 0）
