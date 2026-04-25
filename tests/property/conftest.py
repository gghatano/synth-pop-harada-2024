"""hypothesis property test 共通設定と fixture — Issue #34.

このモジュールは tests/property/ 配下の 4 テストファイルで共通して使う
hypothesis 設定・pytest fixture・ヘルパー関数を提供する。

hypothesis 設定方針
--------------------
- ``max_examples=50`` : CI での flaky を防ぎつつ十分な探索を行う
- ``deadline=None``   : SA などの重い処理に時間制限を掛けない
- ``suppress_health_check`` : function_scoped_fixture および too_slow を抑制

共通 fixture
-------------
- ``sample_objective`` : sample_case データから構築した ``ObjectiveState``
- ``sample_arrays``    : sample_case データから生成した ``PopulationArrays``
- ``sample_stats``     : sample_case から読んだ ``InitStats``
- ``objective_input``  : ``ObjectiveState.from_arrays`` に渡す統計テーブル一式
"""

from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import HealthCheck, settings

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
)
from synthpop_jp.optimize.objective import ObjectiveState
from synthpop_jp.optimize.state import PopulationArrays
from synthpop_jp.rng import SeedRegistry

# ---------------------------------------------------------------------------
# hypothesis グローバル設定
# ---------------------------------------------------------------------------

# property テスト全体で共通のデフォルト設定。
# 各テスト関数は @settings(max_examples=...) でこれを上書きできる。
settings.register_profile(
    "property_default",
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
settings.load_profile("property_default")


# ---------------------------------------------------------------------------
# リポジトリルート解決
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


# ---------------------------------------------------------------------------
# 共通型定義
# ---------------------------------------------------------------------------


class ObjectiveInput:
    """ObjectiveState 構築に必要な統計テーブルをまとめた型."""

    def __init__(
        self,
        age_diff_parent_child: list[AgeDiffParentChildRow],
        age_diff_couple: list[AgeDiffCoupleRow],
        demographic_by_age_sex: list[DemographicByAgeSexRow],
    ) -> None:
        self.age_diff_parent_child = age_diff_parent_child
        self.age_diff_couple = age_diff_couple
        self.demographic_by_age_sex = demographic_by_age_sex


# ---------------------------------------------------------------------------
# 共通 Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def sample_stats() -> InitStats:
    """sample_case から読み込んだ統計データ（session スコープ）."""
    return InitStats(
        family_type_counts=load_family_type_counts(_DATA_DIR / "family_type_counts.csv"),
        children_count_dist=load_children_count_dist(_DATA_DIR / "children_count_dist.csv"),
        demographic_by_age_sex=load_demographic_by_age_sex(
            _DATA_DIR / "demographic_by_age_sex.csv"
        ),
        family_type_mapping=load_family_type_mapping(_CONFIGS_DIR / "family_type_mapping.yaml"),
        household_size_by_family_type=load_household_size_by_family_type(
            _DATA_DIR / "household_size_by_family_type.csv"
        ),
        demographic_by_family_type_role=load_demographic_by_family_type_role(
            _DATA_DIR / "demographic_by_family_type_role.csv"
        ),
    )


@pytest.fixture(scope="session")
def objective_input(sample_stats: InitStats) -> ObjectiveInput:
    """ObjectiveState 構築に必要な統計テーブルをまとめた dict（session スコープ）."""
    return ObjectiveInput(
        age_diff_parent_child=load_age_diff_parent_child(_DATA_DIR / "age_diff_parent_child.csv"),
        age_diff_couple=load_age_diff_couple(_DATA_DIR / "age_diff_couple.csv"),
        demographic_by_age_sex=sample_stats.demographic_by_age_sex,
    )


@pytest.fixture
def sample_arrays(sample_stats: InitStats) -> PopulationArrays:
    """sample_case から生成した初期人口（function スコープ、固定 seed）."""
    rng = SeedRegistry(root=42).rng("init")
    return generate_initial_population(sample_stats, rng)


@pytest.fixture
def sample_objective(
    sample_arrays: PopulationArrays, objective_input: ObjectiveInput
) -> ObjectiveState:
    """sample_case から構築した ObjectiveState（function スコープ）.

    hypothesis テストで使うときは ``copy.deepcopy`` して fresh なコピーを作ること。
    """
    return ObjectiveState.from_arrays(
        arrays=sample_arrays,
        age_diff_parent_child=objective_input.age_diff_parent_child,
        age_diff_couple=objective_input.age_diff_couple,
        demographic_by_age_sex=objective_input.demographic_by_age_sex,
    )


# ---------------------------------------------------------------------------
# ヘルパー: fresh コピー生成
# ---------------------------------------------------------------------------


def fresh_objective(
    stats: InitStats,
    inp: ObjectiveInput,
    seed: int = 42,
) -> ObjectiveState:
    """毎回 fresh な ObjectiveState を返すヘルパー.

    hypothesis の各 example で独立した状態を保つために使う。
    """
    rng = SeedRegistry(root=seed).rng("init")
    arrays = generate_initial_population(stats, rng)
    return ObjectiveState.from_arrays(
        arrays=arrays,
        age_diff_parent_child=inp.age_diff_parent_child,
        age_diff_couple=inp.age_diff_couple,
        demographic_by_age_sex=inp.demographic_by_age_sex,
    )


def fresh_arrays(stats: InitStats, seed: int = 42) -> PopulationArrays:
    """毎回 fresh な PopulationArrays を返すヘルパー."""
    rng = SeedRegistry(root=seed).rng("init")
    return generate_initial_population(stats, rng)
