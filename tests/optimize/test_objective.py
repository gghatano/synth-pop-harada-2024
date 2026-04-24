"""Tests for ObjectiveState — 差分更新版目的関数.

TDD サイクル:
  Cycle 1: from_arrays で 5 統計の観測ヒストグラムが初期化され total_score が計算できる
  Cycle 2: propose_change が副作用なし
  Cycle 3: apply_change 後の total_score が before + propose_change に一致
  Cycle 4: apply_change → 元に戻す apply_change で total_score が復元される
  Cycle 5: hypothesis property test — 差分更新 ≡ 全再計算（最重要）
  Cycle 6: pytest-benchmark skeleton — propose_change が 100μs 以下
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

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
from synthpop_jp.optimize.objective import ObjectiveState, build_objective_stats
from synthpop_jp.optimize.state import PopulationArrays
from synthpop_jp.rng import SeedRegistry


# ---------------------------------------------------------------------------
# pyproject.toml 探索によるリポジトリルート解決（docs/rules/tdd.md §10）
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
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def rng() -> np.random.Generator:
    """固定 seed の乱数発生器."""
    return SeedRegistry(root=42).rng("init")


@pytest.fixture
def sample_stats() -> InitStats:
    """sample_case から読み込んだ統計データ."""
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


@pytest.fixture
def sample_arrays(sample_stats: InitStats, rng: np.random.Generator) -> PopulationArrays:
    """sample_case から生成した初期人口."""
    return generate_initial_population(sample_stats, rng)


@pytest.fixture
def objective_input(sample_stats: InitStats):
    """ObjectiveState 構築に必要な統計テーブルをまとめた dict."""
    return {
        "age_diff_parent_child": load_age_diff_parent_child(
            _DATA_DIR / "age_diff_parent_child.csv"
        ),
        "age_diff_couple": load_age_diff_couple(_DATA_DIR / "age_diff_couple.csv"),
        "demographic_by_age_sex": sample_stats.demographic_by_age_sex,
    }


@pytest.fixture
def objective(sample_arrays: PopulationArrays, objective_input: dict) -> ObjectiveState:
    """ObjectiveState を sample_case から初期化."""
    return ObjectiveState.from_arrays(
        arrays=sample_arrays,
        age_diff_parent_child=objective_input["age_diff_parent_child"],
        age_diff_couple=objective_input["age_diff_couple"],
        demographic_by_age_sex=objective_input["demographic_by_age_sex"],
    )


# ---------------------------------------------------------------------------
# Cycle 1: from_arrays で 5 統計が初期化され total_score が計算できる
# ---------------------------------------------------------------------------


class TestFromArrays:
    """ObjectiveState.from_arrays の初期化テスト."""

    def test_total_score_is_nonnegative(self, objective: ObjectiveState) -> None:
        """total_score は L1 ノルムのため非負である."""
        assert objective.total_score >= 0.0

    def test_total_score_is_finite(self, objective: ObjectiveState) -> None:
        """total_score は有限値である（nan/inf でない）."""
        assert np.isfinite(objective.total_score)

    def test_has_five_stat_tables(self, objective: ObjectiveState) -> None:
        """5 統計分の stat テーブルが存在する."""
        assert len(objective.stats) == 5

    def test_observed_counts_are_nonnegative(self, objective: ObjectiveState) -> None:
        """全統計の observed カウントが非負整数である."""
        for stat in objective.stats:
            assert np.all(stat.observed >= 0)

    def test_target_counts_are_nonnegative(self, objective: ObjectiveState) -> None:
        """全統計の target カウントが非負整数である."""
        for stat in objective.stats:
            assert np.all(stat.target >= 0)

    def test_total_score_equals_sum_of_l1_per_stat(self, objective: ObjectiveState) -> None:
        """total_score が各統計の L1 ノルムの合計に一致する."""
        expected = float(
            sum(np.abs(stat.observed.astype(np.int64) - stat.target.astype(np.int64)).sum()
                for stat in objective.stats)
        )
        assert objective.total_score == pytest.approx(expected, abs=1e-6)

    def test_male_pyramid_observed_sum_matches_male_persons(
        self, objective: ObjectiveState, sample_arrays: PopulationArrays
    ) -> None:
        """male pyramid の observed 合計 = 男性人数."""
        n_males = int((sample_arrays.sex == 0).sum())
        # stats[3] は male pyramid
        male_pyramid_observed_sum = int(objective.stats[3].observed.sum())
        assert male_pyramid_observed_sum == n_males

    def test_female_pyramid_observed_sum_matches_female_persons(
        self, objective: ObjectiveState, sample_arrays: PopulationArrays
    ) -> None:
        """female pyramid の observed 合計 = 女性人数."""
        n_females = int((sample_arrays.sex == 1).sum())
        # stats[4] は female pyramid
        female_pyramid_observed_sum = int(objective.stats[4].observed.sum())
        assert female_pyramid_observed_sum == n_females


# ---------------------------------------------------------------------------
# Cycle 2: propose_change が副作用なし
# ---------------------------------------------------------------------------


class TestProposeChangeNoSideEffect:
    """propose_change は副作用を持たない."""

    def test_propose_does_not_change_total_score(self, objective: ObjectiveState) -> None:
        """propose_change 後も total_score が変わらない."""
        before = objective.total_score
        # 最初の person の age を 1 増やす提案
        new_age = int(objective.arrays.age[0]) + 1
        objective.propose_change(0, new_age)
        assert objective.total_score == before

    def test_propose_does_not_change_arrays_age(self, objective: ObjectiveState) -> None:
        """propose_change 後も arrays.age が変わらない."""
        old_age = int(objective.arrays.age[0])
        new_age = old_age + 1
        objective.propose_change(0, new_age)
        assert int(objective.arrays.age[0]) == old_age

    def test_propose_returns_finite_float(self, objective: ObjectiveState) -> None:
        """propose_change の戻り値は有限の float である."""
        new_age = int(objective.arrays.age[0]) + 1
        delta = objective.propose_change(0, new_age)
        assert isinstance(delta, float)
        assert np.isfinite(delta)

    def test_propose_no_change_returns_zero(self, objective: ObjectiveState) -> None:
        """age を変えない propose_change の差分は 0 である."""
        current_age = int(objective.arrays.age[0])
        delta = objective.propose_change(0, current_age)
        assert delta == pytest.approx(0.0, abs=1e-9)


# ---------------------------------------------------------------------------
# Cycle 3: apply_change 後の total_score が before + propose_change に一致
# ---------------------------------------------------------------------------


class TestApplyChangeConsistency:
    """apply_change と propose_change の整合性テスト."""

    def test_apply_change_updates_total_score_consistently(
        self, objective: ObjectiveState
    ) -> None:
        """apply_change 後の total_score = before + propose_change."""
        before_score = objective.total_score
        idx = 0
        new_age = int(objective.arrays.age[idx]) + 2
        delta = objective.propose_change(idx, new_age)
        objective.apply_change(idx, new_age)
        expected = before_score + delta
        assert objective.total_score == pytest.approx(expected, abs=1e-6)

    def test_apply_change_updates_arrays_age(self, objective: ObjectiveState) -> None:
        """apply_change 後は arrays.age が new_age に更新されている."""
        idx = 0
        new_age = int(objective.arrays.age[idx]) + 2
        objective.apply_change(idx, new_age)
        assert int(objective.arrays.age[idx]) == new_age

    def test_apply_change_updates_observed_histogram(self, objective: ObjectiveState) -> None:
        """apply_change 後に observed ヒストグラムが変化している."""
        idx = 0
        old_age = int(objective.arrays.age[idx])
        new_age = old_age + 5

        # male pyramid の観測値を記録
        observed_before = objective.stats[3].observed.copy()
        objective.apply_change(idx, new_age)
        observed_after = objective.stats[3].observed.copy()

        # old_age と new_age が同じビンでない限り変化するはず（男性の場合）
        sex_id = int(objective.arrays.sex[idx])
        if sex_id == 0 and old_age != new_age:  # M
            assert not np.array_equal(observed_before, observed_after)


# ---------------------------------------------------------------------------
# Cycle 4: apply_change → 元に戻す apply_change で total_score が復元される
# ---------------------------------------------------------------------------


class TestApplyChangeReversibility:
    """apply_change の可逆性テスト."""

    def test_apply_and_revert_restores_total_score(self, objective: ObjectiveState) -> None:
        """apply → revert で total_score が元に戻る."""
        original_score = objective.total_score
        idx = 0
        old_age = int(objective.arrays.age[idx])
        new_age = old_age + 3

        objective.apply_change(idx, new_age)
        objective.apply_change(idx, old_age)  # 元に戻す

        assert objective.total_score == pytest.approx(original_score, abs=1e-6)

    def test_apply_and_revert_restores_observed_histograms(
        self, objective: ObjectiveState
    ) -> None:
        """apply → revert で全統計の observed が元に戻る."""
        observed_originals = [stat.observed.copy() for stat in objective.stats]

        idx = 0
        old_age = int(objective.arrays.age[idx])
        new_age = old_age + 3

        objective.apply_change(idx, new_age)
        objective.apply_change(idx, old_age)

        for i, stat in enumerate(objective.stats):
            assert np.array_equal(stat.observed, observed_originals[i]), (
                f"stats[{i}] の observed が復元されていない"
            )

    def test_multiple_apply_and_revert(self, objective: ObjectiveState) -> None:
        """複数回の apply → revert でも total_score が元に戻る."""
        original_score = objective.total_score
        n_persons = objective.arrays.n_persons

        for i in range(min(5, n_persons)):
            old_age = int(objective.arrays.age[i])
            new_age = old_age + 1
            objective.apply_change(i, new_age)

        for i in range(min(5, n_persons) - 1, -1, -1):
            old_age = int(objective.arrays.age[i]) - 1  # apply 前の値
            objective.apply_change(i, old_age)

        assert objective.total_score == pytest.approx(original_score, abs=1e-6)


# ---------------------------------------------------------------------------
# Cycle 5: hypothesis property test — 差分更新 ≡ 全再計算（最重要）
# ---------------------------------------------------------------------------


def _full_recompute_score(
    arrays: PopulationArrays,
    age_diff_parent_child,
    age_diff_couple,
    demographic_by_age_sex,
) -> float:
    """全再計算でスコアを求めるヘルパー（property test 用）."""
    fresh = ObjectiveState.from_arrays(
        arrays=arrays,
        age_diff_parent_child=age_diff_parent_child,
        age_diff_couple=age_diff_couple,
        demographic_by_age_sex=demographic_by_age_sex,
    )
    return fresh.total_score


class TestDifferentialUpdateEqualsFullRecompute:
    """差分更新が全再計算と bitwise 一致することを確認する（最重要テスト）."""

    def test_propose_equals_full_recompute_delta_single(
        self, objective: ObjectiveState, objective_input: dict
    ) -> None:
        """単一の propose_change が全再計算差分に一致する（固定ケース）."""
        idx = 0
        new_age = min(int(objective.arrays.age[idx]) + 5, 80)

        # 差分更新で計算
        delta_differential = objective.propose_change(idx, new_age)
        score_before = objective.total_score

        # 全再計算: age を変えた配列で再初期化
        old_age = int(objective.arrays.age[idx])
        objective.arrays.age[idx] = np.int16(new_age)
        score_after_full = _full_recompute_score(
            objective.arrays,
            objective_input["age_diff_parent_child"],
            objective_input["age_diff_couple"],
            objective_input["demographic_by_age_sex"],
        )
        objective.arrays.age[idx] = np.int16(old_age)  # 元に戻す

        expected_delta = score_after_full - score_before
        assert delta_differential == pytest.approx(expected_delta, abs=1e-6)

    @given(
        person_idx_frac=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        new_age=st.integers(min_value=0, max_value=100),
    )
    @settings(max_examples=50, deadline=5000)
    def test_propose_equals_full_recompute_delta_property(
        self,
        person_idx_frac: float,
        new_age: int,
        objective_input: dict,
        sample_stats: InitStats,
    ) -> None:
        """任意の (person_idx, new_age) で propose_change が全再計算差分に一致する."""
        # 毎回 fresh な ObjectiveState と PopulationArrays を生成
        rng = SeedRegistry(root=42).rng("init")
        arrays = generate_initial_population(sample_stats, rng)
        obj = ObjectiveState.from_arrays(
            arrays=arrays,
            age_diff_parent_child=objective_input["age_diff_parent_child"],
            age_diff_couple=objective_input["age_diff_couple"],
            demographic_by_age_sex=objective_input["demographic_by_age_sex"],
        )

        n_persons = obj.arrays.n_persons
        idx = max(0, min(int(person_idx_frac * n_persons), n_persons - 1))
        score_before = obj.total_score

        # 差分更新で delta を計算
        delta_differential = obj.propose_change(idx, new_age)

        # 全再計算: age を変えた配列で再初期化
        old_age = int(obj.arrays.age[idx])
        obj.arrays.age[idx] = np.int16(new_age)
        score_after_full = _full_recompute_score(
            obj.arrays,
            objective_input["age_diff_parent_child"],
            objective_input["age_diff_couple"],
            objective_input["demographic_by_age_sex"],
        )
        obj.arrays.age[idx] = np.int16(old_age)  # 元に戻す

        expected_delta = score_after_full - score_before
        assert delta_differential == pytest.approx(expected_delta, abs=1e-6), (
            f"idx={idx}, old_age={old_age}, new_age={new_age}: "
            f"differential={delta_differential:.6f}, full={expected_delta:.6f}"
        )

    @given(
        person_idx_frac=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        new_age=st.integers(min_value=0, max_value=100),
    )
    @settings(max_examples=30, deadline=5000)
    def test_apply_then_revert_restores_score_property(
        self,
        person_idx_frac: float,
        new_age: int,
        objective_input: dict,
        sample_stats: InitStats,
    ) -> None:
        """apply → revert で total_score が元に戻る（property test）."""
        rng = SeedRegistry(root=42).rng("init")
        arrays = generate_initial_population(sample_stats, rng)
        obj = ObjectiveState.from_arrays(
            arrays=arrays,
            age_diff_parent_child=objective_input["age_diff_parent_child"],
            age_diff_couple=objective_input["age_diff_couple"],
            demographic_by_age_sex=objective_input["demographic_by_age_sex"],
        )

        n_persons = obj.arrays.n_persons
        idx = max(0, min(int(person_idx_frac * n_persons), n_persons - 1))
        original_score = obj.total_score
        old_age = int(obj.arrays.age[idx])

        obj.apply_change(idx, new_age)
        obj.apply_change(idx, old_age)

        assert obj.total_score == pytest.approx(original_score, abs=1e-6), (
            f"idx={idx}, old_age={old_age}, new_age={new_age}: "
            f"restored={obj.total_score:.6f}, original={original_score:.6f}"
        )


# ---------------------------------------------------------------------------
# Cycle 6: pytest-benchmark skeleton — propose_change が 100μs 以下
# ---------------------------------------------------------------------------


class TestPerformanceSkeleton:
    """propose_change の性能テスト（skeleton）."""

    def test_propose_change_is_fast_skeleton(self, objective: ObjectiveState) -> None:
        """propose_change が 1000 回実行できる（性能の sanity check）.

        本格計測は Issue #6 で pytest-benchmark を使う。
        ここでは 1000 回のループが 1 秒以内に終わることを確認する。
        """
        import time

        n_persons = objective.arrays.n_persons
        n_trials = 1000

        start = time.perf_counter()
        for i in range(n_trials):
            idx = i % n_persons
            new_age = (int(objective.arrays.age[idx]) + 1) % 80
            objective.propose_change(idx, new_age)
        elapsed = time.perf_counter() - start

        # 1000 回で 1 秒以内 → 平均 1ms/回、100μs 目標より余裕あり
        # （厳密な 100μs/回 の確認は pytest-benchmark で行う）
        avg_us = elapsed / n_trials * 1e6
        assert elapsed < 1.0, (
            f"1000 回の propose_change が {elapsed:.3f} 秒 かかった "
            f"(avg={avg_us:.1f}μs/回)"
        )
