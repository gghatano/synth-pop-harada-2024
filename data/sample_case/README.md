# data/sample_case/

同梱の合成ダミーデータ。`synthpop-jp quickstart` の入力として使われ、テストの fixture でも参照されます。

`scripts/generate_sample_case.py` で seed 固定で生成されており、決定的に再現できます。実データではないので、いかなる個人や世帯にも対応しません。

## ファイル一覧

| ファイル | 列 | 役割 |
|---|---|---|
| `family_type_counts.csv` | `family_type, count` | 9 種の家族類型ごとの世帯数（spec §8.1） |
| `household_size_by_family_type.csv` | `family_type, household_size, count` | 家族類型 × 世帯人数の分布 |
| `demographic_by_age_sex.csv` | `age, sex, count` | 年齢 × 性別の人口ピラミッド |
| `demographic_by_family_type_role.csv` | `family_type, role, sex, age, count` | 家族類型 × 役割 × 性別 × 年齢の同時分布（年齢サンプリングで使用） |
| `age_diff_couple.csv` | `diff_min, diff_max, count` | 夫婦の年齢差ビン別件数 |
| `age_diff_parent_child.csv` | `role, diff_min, diff_max, count` | 親子の年齢差ビン別件数（役割ごと） |
| `children_count_dist.csv` | `family_type_group, n_children, rate` | family_type_group 別の子供数分布（rate） |

## スキーマと意味

各列の型・単位・欠損規則・符号慣習は [`docs/spec/data_contract.md`](../../docs/spec/data_contract.md) に定義されています。本 CSV を改変したり実データに差し替えるときは、まずそのスキーマを満たしているか pydantic ローダで検証してください:

```bash
uv run synthpop-jp validate-config configs/base.yaml
```

## 再生成

```bash
uv run python scripts/generate_sample_case.py
```

seed が固定されているため、出力は bitwise に同じになります（決定性テスト `tests/io/` を参照）。
