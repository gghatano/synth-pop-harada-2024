#!/usr/bin/env python3
"""ダミー入力 CSV を生成するスクリプト.

seed を固定しているため、2 回実行すると bitwise 一致する CSV が得られる。

使い方::

    uv run python scripts/generate_sample_case.py
    uv run python scripts/generate_sample_case.py --output-dir data/sample_case

生成ファイル:
    - family_type_counts.csv      : 9 種類の家族類型の世帯数（合計 100 世帯）
    - children_count_dist.csv     : 家族類型グループ別・子ども人数分布
    - demographic_by_age_sex.csv  : 年齢 × 性別の人口
    - age_diff_parent_child.csv   : 親子年齢差の分布
    - age_diff_couple.csv         : 夫婦年齢差の分布
    - demographic_by_family_type_role.csv  : 家族類型 × 役割 × 性別 × 年齢の人口
    - household_size_by_family_type.csv    : 家族類型別世帯人数分布

再現性の保証:
    - 乱数源: ``numpy.random.Generator``（``SeedSequence`` で seed を固定）
    - SEED = 42 を使う
    - numpy バージョンと seed が同じなら bitwise 一致する
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

Row = dict[str, Any]

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

SEED = 42

FAMILY_TYPES = [
    "single",
    "couple",
    "couple_and_children",
    "father_and_children",
    "mother_and_children",
    "couple_and_parents",
    "couple_and_a_parent",
    "couple_children_and_parents",
    "couple_children_and_a_parent",
]

# 9 種類の家族類型を 3 グループに分類（configs/family_type_mapping.yaml と一致）
FAMILY_TYPE_GROUPS: dict[str, str] = {
    "single": "single",
    "couple": "without_children",
    "couple_and_children": "with_children",
    "father_and_children": "with_children",
    "mother_and_children": "with_children",
    "couple_and_parents": "without_children",
    "couple_and_a_parent": "without_children",
    "couple_children_and_parents": "with_children",
    "couple_children_and_a_parent": "with_children",
}

# family_type_group ごとの代表的な役割構成
ROLES_BY_FAMILY_TYPE: dict[str, list[str]] = {
    "single": ["single"],
    "couple": ["husband", "wife"],
    "couple_and_children": ["husband", "wife", "child"],
    "father_and_children": ["father", "child"],
    "mother_and_children": ["mother", "child"],
    "couple_and_parents": ["husband", "wife", "parent"],
    "couple_and_a_parent": ["husband", "wife", "parent"],
    "couple_children_and_parents": ["husband", "wife", "child", "parent"],
    "couple_children_and_a_parent": ["husband", "wife", "child", "parent"],
}

# 100 世帯の構成比（各型の世帯数）
HOUSEHOLD_COUNTS_WEIGHTS = [15, 20, 30, 5, 8, 5, 5, 7, 5]


# ---------------------------------------------------------------------------
# 生成関数
# ---------------------------------------------------------------------------


def _generate_family_type_counts(rng: np.random.Generator) -> pd.DataFrame:
    """family_type_counts.csv 相当のデータを生成する.

    合計 100 世帯として、9 種類の家族類型に按分する。
    weights から multinomial で生成し再現性を保証する。
    """
    weights = np.array(HOUSEHOLD_COUNTS_WEIGHTS, dtype=float)
    probs = weights / weights.sum()
    counts = rng.multinomial(100, probs)
    return pd.DataFrame({"family_type": FAMILY_TYPES, "count": counts.tolist()})


def _generate_children_count_dist(rng: np.random.Generator) -> pd.DataFrame:
    """children_count_dist.csv 相当のデータを生成する.

    family_type_group 別・子ども人数（1〜4 人）の分布を生成する。
    with_children グループのみ対象。
    """
    rows: list[Row] = []
    # with_children: 1〜4 人の分布（合計 1.0）
    alphas_with = np.array([4.0, 3.0, 2.0, 1.0])
    rates_with = rng.dirichlet(alphas_with)
    for n, r in enumerate(rates_with, start=1):
        rows.append({"family_type_group": "with_children", "n_children": n, "rate": float(r)})

    # without_children: 子ども 0 人のみ（rate = 1.0）
    rows.append({"family_type_group": "without_children", "n_children": 0, "rate": 1.0})

    # single: 子ども 0 人のみ（rate = 1.0）
    rows.append({"family_type_group": "single", "n_children": 0, "rate": 1.0})

    return pd.DataFrame(rows)


def _generate_demographic_by_age_sex(rng: np.random.Generator) -> pd.DataFrame:
    """demographic_by_age_sex.csv 相当のデータを生成する.

    0〜90 歳（5 歳刻み）× 性別の人口を生成する。
    単純な正規分布から生成し、合計が約 300 人程度になるよう調整。
    """
    rows: list[Row] = []
    age_bins = list(range(0, 91, 5))
    for sex in ("M", "F"):
        # 年齢分布: ピークが 35〜45 歳の正規分布に近い形
        mean_age = 38.0 if sex == "M" else 36.0
        std_age = 20.0
        probs = np.exp(-0.5 * ((np.array(age_bins, dtype=float) - mean_age) / std_age) ** 2)
        probs = probs / probs.sum()
        total = 150  # 性別ごとの合計人口
        counts = rng.multinomial(total, probs)
        for age, count in zip(age_bins, counts.tolist(), strict=True):
            rows.append({"age": age, "sex": sex, "count": count})
    return pd.DataFrame(rows)


def _generate_age_diff_parent_child(rng: np.random.Generator) -> pd.DataFrame:
    """age_diff_parent_child.csv 相当のデータを生成する.

    親子年齢差（parent_age - child_age）を 5 歳刻みの半開区間で表現する。
    父 / 母 それぞれについて 20〜45 歳差のビンを生成する。
    """
    rows: list[Row] = []
    diff_bins = list(range(15, 51, 5))  # [15, 20, 25, ..., 50]

    for role in ("father", "mother"):
        # 親子年齢差: 平均 27 歳差（父）/ 25 歳差（母）の正規分布
        mean_diff = 27.0 if role == "father" else 25.0
        std_diff = 5.0
        probs = np.exp(-0.5 * ((np.array(diff_bins, dtype=float) - mean_diff) / std_diff) ** 2)
        probs = probs / probs.sum()
        total = 80
        counts = rng.multinomial(total, probs)
        for i, (diff_min, count) in enumerate(zip(diff_bins, counts.tolist(), strict=True)):
            diff_max = diff_bins[i + 1] if i + 1 < len(diff_bins) else diff_min + 5
            rows.append({"role": role, "diff_min": diff_min, "diff_max": diff_max, "count": count})

    return pd.DataFrame(rows)


def _generate_age_diff_couple(rng: np.random.Generator) -> pd.DataFrame:
    """age_diff_couple.csv 相当のデータを生成する.

    couple_diff = husband_age - wife_age（夫の年齢 − 妻の年齢）。
    夫が年上なら正、妻が年上なら負（data_contract.md §4 参照）。
    −15〜+20 歳差の 5 歳刻みビンを生成する。
    """
    rows: list[Row] = []
    diff_bins = list(range(-15, 21, 5))  # [-15, -10, -5, 0, 5, 10, 15, 20]

    # couple_diff 分布: 平均 3 歳（夫が年上）の正規分布
    mean_diff = 3.0
    std_diff = 5.0
    probs = np.exp(-0.5 * ((np.array(diff_bins, dtype=float) - mean_diff) / std_diff) ** 2)
    probs = probs / probs.sum()
    total = 60
    counts = rng.multinomial(total, probs)

    for i, (diff_min, count) in enumerate(zip(diff_bins, counts.tolist(), strict=True)):
        diff_max = diff_bins[i + 1] if i + 1 < len(diff_bins) else diff_min + 5
        rows.append({"diff_min": diff_min, "diff_max": diff_max, "count": count})

    return pd.DataFrame(rows)


def _generate_demographic_by_family_type_role(rng: np.random.Generator) -> pd.DataFrame:
    """demographic_by_family_type_role.csv 相当のデータを生成する（任意入力）.

    family_type × role × sex × age の人口を生成する。
    各組み合わせで数人程度の人口を割り当てる。
    """
    rows: list[Row] = []
    age_bins = [20, 30, 40, 50, 60, 70]

    for ft in FAMILY_TYPES:
        roles = ROLES_BY_FAMILY_TYPE[ft]
        for role in roles:
            # 役割に応じた性別
            if role in ("husband", "father", "single"):
                sexes = ["M"]
            elif role in ("wife", "mother"):
                sexes = ["F"]
            elif role == "child":
                sexes = ["M", "F"]
            else:  # parent
                sexes = ["M", "F"]

            for sex in sexes:
                # 年齢分布: 役割に応じた中心年齢
                if role in ("husband", "father"):
                    center = 42.0
                elif role in ("wife", "mother"):
                    center = 39.0
                elif role == "child":
                    center = 12.0
                elif role == "parent":
                    center = 68.0
                else:  # single
                    center = 40.0

                std = 10.0
                probs = np.exp(-0.5 * ((np.array(age_bins, dtype=float) - center) / std) ** 2)
                probs = probs / probs.sum()
                total = max(1, int(rng.integers(5, 15)))
                counts = rng.multinomial(total, probs)
                for age, count in zip(age_bins, counts.tolist(), strict=True):
                    if count > 0:
                        rows.append(
                            {
                                "family_type": ft,
                                "role": role,
                                "sex": sex,
                                "age": age,
                                "count": count,
                            }
                        )

    return pd.DataFrame(rows)


def _generate_household_size_by_family_type(rng: np.random.Generator) -> pd.DataFrame:
    """household_size_by_family_type.csv 相当のデータを生成する（任意入力）.

    family_type 別・世帯人数の分布を生成する。
    """
    rows: list[Row] = []
    # 家族類型ごとの典型的な世帯人数
    size_templates: dict[str, list[int]] = {
        "single": [1],
        "couple": [2],
        "couple_and_children": [3, 4, 5],
        "father_and_children": [2, 3, 4],
        "mother_and_children": [2, 3, 4],
        "couple_and_parents": [3, 4],
        "couple_and_a_parent": [3],
        "couple_children_and_parents": [4, 5, 6],
        "couple_children_and_a_parent": [4, 5],
    }

    for ft, sizes in size_templates.items():
        probs = rng.dirichlet(np.ones(len(sizes)))
        total = 20
        counts = rng.multinomial(total, probs)
        for size, count in zip(sizes, counts.tolist(), strict=True):
            rows.append({"family_type": ft, "household_size": size, "count": count})

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# メイン
# ---------------------------------------------------------------------------


def generate(output_dir: Path) -> None:
    """全 CSV を生成して output_dir に保存する."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # 再現性: SeedSequence で 7 つのサブ RNG を生成
    ss = np.random.SeedSequence(SEED)
    rng_ftc, rng_ccd, rng_dem, rng_apc, rng_adc, rng_dftr, rng_hsft = (
        np.random.default_rng(child) for child in ss.spawn(7)
    )

    datasets: dict[str, pd.DataFrame] = {
        "family_type_counts.csv": _generate_family_type_counts(rng_ftc),
        "children_count_dist.csv": _generate_children_count_dist(rng_ccd),
        "demographic_by_age_sex.csv": _generate_demographic_by_age_sex(rng_dem),
        "age_diff_parent_child.csv": _generate_age_diff_parent_child(rng_apc),
        "age_diff_couple.csv": _generate_age_diff_couple(rng_adc),
        "demographic_by_family_type_role.csv": _generate_demographic_by_family_type_role(rng_dftr),
        "household_size_by_family_type.csv": _generate_household_size_by_family_type(rng_hsft),
    }

    for filename, df in datasets.items():
        out_path = output_dir / filename
        df.to_csv(out_path, index=False)  # type: ignore[reportUnknownMemberType]
        print(f"  wrote {out_path} ({len(df)} rows)")


def main() -> None:
    """CLI エントリポイント."""
    parser = argparse.ArgumentParser(
        description="seed 固定のダミー入力 CSV を生成する（2 回実行で bitwise 一致）"
    )
    parser.add_argument(
        "--output-dir",
        default="data/sample_case",
        help="出力先ディレクトリ（デフォルト: data/sample_case）",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    print(f"Generating sample case CSVs (seed={SEED}) -> {output_dir}")
    generate(output_dir)
    print("Done.")


if __name__ == "__main__":
    main()
