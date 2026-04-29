"""Tests for make_inputs (Issue #51).

実験ユーティリティのテスト。明示的にパス指定で起動する:
``uv run pytest experiments/2026-04-29-sa-memory-profile/test_make_inputs.py``
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from make_inputs import COPY_CSVS, COUNT_CSVS, generate


def test_generate_produces_all_seven_csvs(tmp_path: Path) -> None:
    """7 種の入力 CSV すべてを target_dir に書き出す."""
    target_dir = tmp_path / "data_1k"
    generate(target_n_households=1_000, target_dir=target_dir)

    for name in COUNT_CSVS + COPY_CSVS:
        assert (target_dir / name).exists(), f"{name} が生成されていない"


def test_generate_scales_household_total(tmp_path: Path) -> None:
    """family_type_counts の合計が target_n_households と一致する."""
    target_dir = tmp_path / "data_10k"
    generate(target_n_households=10_000, target_dir=target_dir)

    df = pd.read_csv(target_dir / "family_type_counts.csv")
    assert int(df["count"].sum()) == 10_000


def test_generate_preserves_rate_csv(tmp_path: Path) -> None:
    """children_count_dist.csv の rate 列はスケール影響を受けない."""
    target_dir = tmp_path / "data_1k"
    generate(target_n_households=1_000, target_dir=target_dir)

    df_orig = pd.read_csv(
        Path(__file__).resolve().parents[2] / "data" / "sample_case" / "children_count_dist.csv"
    )
    df_out = pd.read_csv(target_dir / "children_count_dist.csv")
    pd.testing.assert_frame_equal(df_orig, df_out)


def test_generate_rejects_non_multiple_of_100(tmp_path: Path) -> None:
    """100 の倍数でない世帯数は ValueError."""
    with pytest.raises(ValueError, match="multiple of 100"):
        generate(target_n_households=999, target_dir=tmp_path / "bad")
