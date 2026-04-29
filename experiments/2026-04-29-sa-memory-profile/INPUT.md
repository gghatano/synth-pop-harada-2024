# 入力データの生成方法（Issue #51）

本実験は固定の入力データを使わず、`make_inputs.py` がリポジトリ同梱の
`data/sample_case/` を整数倍スケールして tempdir 内に動的生成する。

## 元データ

- 名前: synthpop-jp sample_case
- 場所: リポジトリ直下 `data/sample_case/`
- 世帯数: 100（`family_type_counts.csv` の合計）
- 内容: 7 つの目標統計 CSV（family_type / household_size / demographic_age_sex /
  demographic_family_type_role / age_diff_couple / age_diff_parent_child /
  children_count_dist）

## スケール戦略

`count` 列を `target_n_households / 100` 倍する。`rate` 列はそのまま。

| ファイル | スケール対象列 |
|---|---|
| family_type_counts.csv | count |
| household_size_by_family_type.csv | count |
| demographic_by_age_sex.csv | count |
| demographic_by_family_type_role.csv | count |
| age_diff_couple.csv | count |
| age_diff_parent_child.csv | count |
| children_count_dist.csv | （rate 列のみ、不変） |

スケール係数が整数になるよう、`target_n_households` は 100 の倍数に限定する
（`make_inputs.py::generate` が `ValueError` で弾く）。

## 再生成手順

```python
from pathlib import Path
import sys
sys.path.insert(0, "experiments/2026-04-29-sa-memory-profile")
from make_inputs import generate

generate(target_n_households=100_000, target_dir=Path("/tmp/data_100k"))
```

または `run.py` 経由で各セル実行ごとに自動生成される。

## 乱数 seed

`make_inputs.py` 自体は決定論的（乱数を使わない）。SA の seed は
`run.py` の `--seeds` で指定し、各セルの config.yaml に渡される。
本実験では {1, 2, 3} を使用（一部セルのみ seed×3）。

## データ規模

| target_n_households | 生成 CSV 合計サイズ（推定） |
|---|---|
| 1,000 | ~1KB |
| 10,000 | ~10KB |
| 100,000 | ~100KB |

入力 CSV 自体は小さく、git に commit しなくても tempdir で完結する。
