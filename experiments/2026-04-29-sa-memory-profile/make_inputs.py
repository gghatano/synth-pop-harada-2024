"""Scale sample_case input CSVs to a target household count — Issue #51.

``data/sample_case/`` は 100 世帯ベース。整数倍スケールで 1k / 10k / 100k 規模の
ダミー入力を生成する。``count`` 列のみ整数倍し、``rate`` 列（``children_count_dist.csv``）は
不変。

スケール戦略の理由:
- 内部整合性が崩れない（family_type_counts と demographic_by_family_type_role の和が一致）
- 整数倍ならば丸め誤差が出ない
- メモリ計測実験の目的（規模に対する RSS の傾向）には十分
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_CASE_DIR = REPO_ROOT / "data" / "sample_case"
SAMPLE_CASE_HOUSEHOLDS = 100

COUNT_CSVS = (
    "family_type_counts.csv",
    "household_size_by_family_type.csv",
    "demographic_by_age_sex.csv",
    "demographic_by_family_type_role.csv",
    "age_diff_couple.csv",
    "age_diff_parent_child.csv",
)
COPY_CSVS = ("children_count_dist.csv",)


def generate(target_n_households: int, target_dir: Path) -> None:
    """Generate scaled input CSVs for ``target_n_households`` households.

    Parameters
    ----------
    target_n_households : int
        Desired total number of households. Must be an integer multiple of 100.
    target_dir : Path
        Output directory. Created if it does not exist.

    Raises
    ------
    ValueError
        If ``target_n_households`` is not a positive multiple of 100.
    """
    if target_n_households <= 0 or target_n_households % SAMPLE_CASE_HOUSEHOLDS != 0:
        msg = (
            f"target_n_households must be a positive multiple of {SAMPLE_CASE_HOUSEHOLDS}, "
            f"got {target_n_households}"
        )
        raise ValueError(msg)

    scale = target_n_households // SAMPLE_CASE_HOUSEHOLDS
    target_dir.mkdir(parents=True, exist_ok=True)

    for csv_name in COUNT_CSVS:
        df = pd.read_csv(SAMPLE_CASE_DIR / csv_name)
        df["count"] = df["count"] * scale
        df.to_csv(target_dir / csv_name, index=False)

    for csv_name in COPY_CSVS:
        shutil.copy(SAMPLE_CASE_DIR / csv_name, target_dir / csv_name)
