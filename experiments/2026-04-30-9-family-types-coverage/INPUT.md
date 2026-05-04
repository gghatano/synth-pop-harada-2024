# 入力データの説明 (Issue #95)

## 使用データ

- データ名: synthpop-jp 同梱サンプルデータ（`data/sample_case/`）
- 世帯数: 100 世帯（9 family_types を網羅したダミー）
- 取得方法: リポジトリ内に直接含まれるダミー（実際の国勢調査ではない）

## ファイル一覧

| ファイル | 内容 |
|---|---|
| `family_type_counts.csv` | 9 family_types の世帯数 |
| `household_size_by_family_type.csv` | family_type × 世帯規模 |
| `demographic_by_age_sex.csv` | 性別 × 年齢の人口ピラミッド |
| `demographic_by_family_type_role.csv` | family_type × role × 性別 × 年齢 |
| `age_diff_couple.csv` | 夫婦の年齢差分布 |
| `age_diff_parent_child.csv` | 親子の年齢差分布 |
| `children_count_dist.csv` | 子ども数の分布 |

## 仮説

- 9 family_types すべてが SA 経路を通り、family_type ごとの F-W L1 が悪化しない
- `use_zero_error_init=True` で初期 F-W L1=0 から始める

## 設定

- 目的関数: extended (`use_family_type_pyramid=True`、5+18=23 統計)
- 遷移: `AgeChangeTransition`
- 冷却: `ExponentialCooling(T0=1.0, alpha=0.999)`
- 反復: `max_iters=20000`

## 再現性の指紋（spec §19.3 / Issue #115）

- seed: [42, 43, 44, 45, 46]
- commit_sha: 9d188c5 (本実験を追加したコミット、PR #104 / Issue #95)
- uv_lock_sha256: dda09efe4af1e31e4f985b2b8b513267f79cfc94dce3856e678347d8def8fa82

## 再現コマンド

```bash
uv run python experiments/2026-04-30-9-family-types-coverage/run.py
```
