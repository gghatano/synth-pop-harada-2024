"""ベンチマークテスト共有 fixtures (Issue #33).

このモジュールは 3 種のベンチマークテストが共通で使う fixture を定義する。

設計方針
--------
- 1000 世帯規模の人口を生成するため、sample_case データを 10 倍スケールして使う
- fixture は module スコープにして benchmark 間でデータを共有する
- SA のフル計測は pedantic(rounds=3) で複数回実行して安定した値を得る
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from synthpop_jp.config import AnnealingConfig
from synthpop_jp.init.initial_population import InitStats, generate_initial_population
from synthpop_jp.io.loaders import (
    load_age_diff_couple,
    load_age_diff_parent_child,
    load_children_count_dist,
    load_demographic_by_age_sex,
    load_demographic_by_family_type_role,
    load_family_type_counts,
    load_family_type_mapping,
    load_household_size_by_family_type,
)
from synthpop_jp.io.schemas import (
    AgeDiffCoupleRow,
    AgeDiffParentChildRow,
    DemographicByAgeSexRow,
    FamilyTypeCountRow,
)
from synthpop_jp.optimize.annealing import SARunner
from synthpop_jp.optimize.cooling import ExponentialCooling
from synthpop_jp.optimize.objective import ObjectiveState
from synthpop_jp.optimize.state import PopulationArrays
from synthpop_jp.optimize.transitions import AgeChangeTransition
from synthpop_jp.rng import SeedRegistry

# ---------------------------------------------------------------------------
# pyproject.toml 探索によるリポジトリルート解決
# ---------------------------------------------------------------------------


def _find_repo_root() -> Path:
    """pyproject.toml を含む最近接の祖先を repo root とみなす."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError(f"pyproject.toml が {here} から辿れない階層に見つからない")


_REPO_ROOT = _find_repo_root()
_DATA_DIR = _REPO_ROOT / "data" / "sample_case"
_CONFIGS_DIR = _REPO_ROOT / "configs"

#: ベンチマーク用の世帯数スケール倍率（100 世帯 × 10 = 1000 世帯）
_SCALE_FACTOR = 10


def _scale_family_type_counts(
    rows: list[FamilyTypeCountRow],
    scale: int,
) -> list[FamilyTypeCountRow]:
    """family_type_counts を scale 倍して 1000 世帯規模にする.

    sample_case は 100 世帯規模。scale=10 で 1000 世帯になる。

    Parameters
    ----------
    rows : list[FamilyTypeCountRow]
        元の family_type_counts。
    scale : int
        スケール倍率。

    Returns
    -------
    list[FamilyTypeCountRow]
        count が scale 倍された新しいリスト。
    """
    return [FamilyTypeCountRow(family_type=r.family_type, count=r.count * scale) for r in rows]


def _scale_demographic_by_age_sex(
    rows: list[DemographicByAgeSexRow],
    scale: int,
) -> list[DemographicByAgeSexRow]:
    """demographic_by_age_sex を scale 倍する."""
    return [DemographicByAgeSexRow(age=r.age, sex=r.sex, count=r.count * scale) for r in rows]


def _scale_age_diff_couple(
    rows: list[AgeDiffCoupleRow],
    scale: int,
) -> list[AgeDiffCoupleRow]:
    """age_diff_couple を scale 倍する."""
    return [
        AgeDiffCoupleRow(
            diff_min=r.diff_min,
            diff_max=r.diff_max,
            count=r.count * scale,
        )
        for r in rows
    ]


def _scale_age_diff_parent_child(
    rows: list[AgeDiffParentChildRow],
    scale: int,
) -> list[AgeDiffParentChildRow]:
    """age_diff_parent_child を scale 倍する."""
    return [
        AgeDiffParentChildRow(
            role=r.role,
            diff_min=r.diff_min,
            diff_max=r.diff_max,
            count=r.count * scale,
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# SASetup: SA に必要な全コンポーネントをまとめたデータクラス
# ---------------------------------------------------------------------------


@dataclass
class SASetup:
    """SA ベンチマーク実行に必要な全コンポーネントのコンテナ.

    Attributes
    ----------
    arrays : PopulationArrays
        1000 世帯規模の人口配列。
    objective : ObjectiveState
        差分更新版目的関数の状態。
    transition : AgeChangeTransition
        年齢変更遷移演算子。
    cooling : ExponentialCooling
        指数冷却スケジュール。
    config : AnnealingConfig
        SA 実行パラメータ。
    runner : SARunner
        SA ループ実行器。
    """

    arrays: PopulationArrays
    objective: ObjectiveState
    transition: AgeChangeTransition
    cooling: ExponentialCooling
    config: AnnealingConfig
    runner: SARunner


# ---------------------------------------------------------------------------
# 共有 Fixtures（module スコープ: ベンチマーク間でデータ共有）
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def bench_stats_1000() -> InitStats:
    """1000 世帯規模の InitStats を構築する（sample_case × 10）."""
    raw_ft_counts = load_family_type_counts(_DATA_DIR / "family_type_counts.csv")
    raw_demo = load_demographic_by_age_sex(_DATA_DIR / "demographic_by_age_sex.csv")

    scaled_ft_counts = _scale_family_type_counts(raw_ft_counts, _SCALE_FACTOR)
    scaled_demo = _scale_demographic_by_age_sex(raw_demo, _SCALE_FACTOR)

    return InitStats(
        family_type_counts=scaled_ft_counts,
        children_count_dist=load_children_count_dist(_DATA_DIR / "children_count_dist.csv"),
        demographic_by_age_sex=scaled_demo,
        family_type_mapping=load_family_type_mapping(_CONFIGS_DIR / "family_type_mapping.yaml"),
        household_size_by_family_type=load_household_size_by_family_type(
            _DATA_DIR / "household_size_by_family_type.csv"
        ),
        demographic_by_family_type_role=load_demographic_by_family_type_role(
            _DATA_DIR / "demographic_by_family_type_role.csv"
        ),
    )


@pytest.fixture(scope="module")
def bench_arrays_1000(bench_stats_1000: InitStats) -> PopulationArrays:
    """1000 世帯規模の PopulationArrays を生成する."""
    rng = SeedRegistry(root=42).rng("bench_init")
    return generate_initial_population(bench_stats_1000, rng)


@pytest.fixture(scope="module")
def bench_objective_data_1000() -> tuple[
    list[AgeDiffParentChildRow],
    list[AgeDiffCoupleRow],
    list[DemographicByAgeSexRow],
]:
    """1000 世帯規模の ObjectiveState 構築に必要な統計テーブル（スケール済み）."""
    raw_demo = load_demographic_by_age_sex(_DATA_DIR / "demographic_by_age_sex.csv")
    raw_couple = load_age_diff_couple(_DATA_DIR / "age_diff_couple.csv")
    raw_pc = load_age_diff_parent_child(_DATA_DIR / "age_diff_parent_child.csv")

    return (
        _scale_age_diff_parent_child(raw_pc, _SCALE_FACTOR),
        _scale_age_diff_couple(raw_couple, _SCALE_FACTOR),
        _scale_demographic_by_age_sex(raw_demo, _SCALE_FACTOR),
    )


@pytest.fixture(scope="module")
def sample_objective(
    bench_arrays_1000: PopulationArrays,
    bench_objective_data_1000: tuple[
        list[AgeDiffParentChildRow],
        list[AgeDiffCoupleRow],
        list[DemographicByAgeSexRow],
    ],
) -> ObjectiveState:
    """1000 世帯規模の ObjectiveState を返す（benchmark 用）."""
    age_diff_pc, age_diff_couple, demo = bench_objective_data_1000
    return ObjectiveState.from_arrays(
        arrays=bench_arrays_1000,
        age_diff_parent_child=age_diff_pc,
        age_diff_couple=age_diff_couple,
        demographic_by_age_sex=demo,
    )


@pytest.fixture(scope="module")
def sample_transition(bench_arrays_1000: PopulationArrays) -> AgeChangeTransition:
    """1000 世帯規模の AgeChangeTransition を返す（benchmark 用）."""
    raw_demo = load_demographic_by_age_sex(_DATA_DIR / "demographic_by_age_sex.csv")
    rng = SeedRegistry(root=42).rng("bench_transition")
    return AgeChangeTransition(
        arrays=bench_arrays_1000,
        demo_by_age_sex=raw_demo,
        rng=rng,
    )


@pytest.fixture(scope="module")
def sample_setup(
    bench_arrays_1000: PopulationArrays,
    sample_objective: ObjectiveState,
    sample_transition: AgeChangeTransition,
) -> SASetup:
    """SA ベンチマーク実行に必要な全コンポーネント一式を返す."""
    cooling = ExponentialCooling(T0=100.0, alpha=0.9999)
    config = AnnealingConfig(
        T0=100.0,
        alpha=0.9999,
        max_iters=200_000,
        evals_per_agent=0,
        target_threshold=0.0,
        patience=0,
        trace_enabled=False,
        checkpoint_every_n_iters=0,
        checkpoint_dir=None,
        log_every_n_iters=10_000,
    )
    rng = SeedRegistry(root=42).rng("bench_runner")
    runner = SARunner(rng=rng)
    return SASetup(
        arrays=bench_arrays_1000,
        objective=sample_objective,
        transition=sample_transition,
        cooling=cooling,
        config=config,
        runner=runner,
    )


@pytest.fixture(scope="module")
def sample_setup_smoke(
    bench_arrays_1000: PopulationArrays,
    bench_objective_data_1000: tuple[
        list[AgeDiffParentChildRow],
        list[AgeDiffCoupleRow],
        list[DemographicByAgeSexRow],
    ],
) -> SASetup:
    """CI smoke 用 SA セットアップ（1 万反復）.

    フル end-to-end ベンチと独立した setup。
    独自の arrays/objective を作ることで state の汚染を避ける。
    """
    raw_demo = load_demographic_by_age_sex(_DATA_DIR / "demographic_by_age_sex.csv")
    rng_init = SeedRegistry(root=99).rng("smoke_init")

    raw_ft_counts = load_family_type_counts(_DATA_DIR / "family_type_counts.csv")
    raw_demo_scaled = _scale_demographic_by_age_sex(
        load_demographic_by_age_sex(_DATA_DIR / "demographic_by_age_sex.csv"),
        _SCALE_FACTOR,
    )
    smoke_stats = InitStats(
        family_type_counts=_scale_family_type_counts(raw_ft_counts, _SCALE_FACTOR),
        children_count_dist=load_children_count_dist(_DATA_DIR / "children_count_dist.csv"),
        demographic_by_age_sex=raw_demo_scaled,
        family_type_mapping=load_family_type_mapping(_CONFIGS_DIR / "family_type_mapping.yaml"),
        household_size_by_family_type=load_household_size_by_family_type(
            _DATA_DIR / "household_size_by_family_type.csv"
        ),
        demographic_by_family_type_role=load_demographic_by_family_type_role(
            _DATA_DIR / "demographic_by_family_type_role.csv"
        ),
    )
    smoke_arrays = generate_initial_population(smoke_stats, rng_init)

    age_diff_pc, age_diff_couple, demo = bench_objective_data_1000
    smoke_objective = ObjectiveState.from_arrays(
        arrays=smoke_arrays,
        age_diff_parent_child=age_diff_pc,
        age_diff_couple=age_diff_couple,
        demographic_by_age_sex=demo,
    )
    rng_trans = SeedRegistry(root=99).rng("smoke_transition")
    smoke_transition = AgeChangeTransition(
        arrays=smoke_arrays,
        demo_by_age_sex=raw_demo,
        rng=rng_trans,
    )

    cooling = ExponentialCooling(T0=100.0, alpha=0.9999)
    config = AnnealingConfig(
        T0=100.0,
        alpha=0.9999,
        max_iters=10_000,
        evals_per_agent=0,
        target_threshold=0.0,
        patience=0,
        trace_enabled=False,
        checkpoint_every_n_iters=0,
        checkpoint_dir=None,
        log_every_n_iters=5_000,
    )
    rng_runner = SeedRegistry(root=99).rng("smoke_runner")
    runner = SARunner(rng=rng_runner)
    return SASetup(
        arrays=smoke_arrays,
        objective=smoke_objective,
        transition=smoke_transition,
        cooling=cooling,
        config=config,
        runner=runner,
    )


@pytest.fixture
def fresh_objective(bench_arrays_1000: PopulationArrays) -> ObjectiveState:
    """毎テスト新鮮な（独立した配列コピーを持つ）ObjectiveState を返す.

    benchmark での in-place 更新が他テストに影響しないよう、
    module スコープとは別に function スコープで配列コピーを使う。
    """
    import copy

    arrays_copy = copy.deepcopy(bench_arrays_1000)
    raw_pc = load_age_diff_parent_child(_DATA_DIR / "age_diff_parent_child.csv")
    raw_couple = load_age_diff_couple(_DATA_DIR / "age_diff_couple.csv")
    raw_demo = load_demographic_by_age_sex(_DATA_DIR / "demographic_by_age_sex.csv")

    scaled_pc = _scale_age_diff_parent_child(raw_pc, _SCALE_FACTOR)
    scaled_couple = _scale_age_diff_couple(raw_couple, _SCALE_FACTOR)
    scaled_demo = _scale_demographic_by_age_sex(raw_demo, _SCALE_FACTOR)

    return ObjectiveState.from_arrays(
        arrays=arrays_copy,
        age_diff_parent_child=scaled_pc,
        age_diff_couple=scaled_couple,
        demographic_by_age_sex=scaled_demo,
    )
