"""Tests for checkpoint save/load and SARunner resume — Issue #32.

TDD サイクル:
  Cycle 1: SAState save/load round-trip
  Cycle 2: PopulationArrays の配列 bitwise 一致
  Cycle 3: ObjectiveState の保存・復元（ヒストグラム + total_score 一致）
  Cycle 4: rng 状態保存・復元（次の sample が bitwise 一致）
  Cycle 5: AnnealingConfig の checkpoint フィールド確認
  Cycle 6: SARunner.run の checkpoint フック（checkpoint_every_n_iters ごとにファイル出力）
  Cycle 7: SARunner.run の resume（resume_from で再開、反復数・rng・best_score が連続）
  Cycle 8: bitwise 一致 regression test（baseline vs split run）
  Cycle 9: 性能 skeleton（1000 世帯で 1 回の checkpoint < 100ms）
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pytest

from synthpop_jp.config import AnnealingConfig
from synthpop_jp.domain.household import Household
from synthpop_jp.domain.person import Person
from synthpop_jp.domain.registry import FamilyTypeRegistry, RoleRegistry, SexRegistry
from synthpop_jp.optimize.annealing import SARunner, SAState
from synthpop_jp.optimize.checkpoint import load_checkpoint, save_checkpoint
from synthpop_jp.optimize.cooling import ExponentialCooling
from synthpop_jp.optimize.objective import ObjectiveState
from synthpop_jp.optimize.state import PopulationArrays

# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------

ALL_ROLES = ["husband", "wife", "father", "mother", "child", "parent", "single"]
ALL_FAMILY_TYPES = [
    "couple",
    "couple_and_children",
    "single",
    "lone_parent_and_children",
    "couple_and_a_parent",
]


def make_registries() -> tuple[FamilyTypeRegistry, RoleRegistry, SexRegistry]:
    """テスト用 Registry を返す."""
    family_reg = FamilyTypeRegistry()
    for ft in ALL_FAMILY_TYPES:
        family_reg.register(ft)
    role_reg = RoleRegistry()
    for r in ALL_ROLES:
        role_reg.register(r)
    sex_reg = SexRegistry()
    return family_reg, role_reg, sex_reg


def make_small_arrays(n_persons: int = 10) -> PopulationArrays:
    """単純な配列を返す（テスト用）.

    全員を単身世帯（single）とする。
    """
    family_reg, role_reg, sex_reg = make_registries()
    households = [
        Household(
            household_id=i + 1,
            family_type="single",
            members=[
                Person(
                    household_id=i + 1,
                    role="single",  # type: ignore[arg-type]
                    sex="M" if i % 2 == 0 else "F",  # type: ignore[arg-type]
                    age=30 + i,
                )
            ],
        )
        for i in range(n_persons)
    ]
    return PopulationArrays.from_households(households, family_reg, role_reg, sex_reg)


def make_couple_arrays() -> PopulationArrays:
    """夫婦世帯を含む配列を返す（テスト用）.

    couple 世帯を 3 世帯作る。
    """
    family_reg, role_reg, sex_reg = make_registries()
    households = [
        Household(
            household_id=i + 1,
            family_type="couple",
            members=[
                Person(
                    household_id=i + 1,
                    role="husband",  # type: ignore[arg-type]
                    sex="M",  # type: ignore[arg-type]
                    age=35 + i,
                ),
                Person(
                    household_id=i + 1,
                    role="wife",  # type: ignore[arg-type]
                    sex="F",  # type: ignore[arg-type]
                    age=32 + i,
                ),
            ],
        )
        for i in range(3)
    ]
    return PopulationArrays.from_households(households, family_reg, role_reg, sex_reg)


def _find_repo_root() -> Path:
    """pyproject.toml を探してリポジトリルートを返す."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    msg = "pyproject.toml が見つかりません"
    raise FileNotFoundError(msg)


# ---------------------------------------------------------------------------
# Cycle 1: SAState save/load round-trip
# ---------------------------------------------------------------------------


class TestSAStateRoundTrip:
    """SAState の save/load round-trip テスト."""

    def test_sastate_roundtrip(self, tmp_path: Path) -> None:
        """SAState が bitwise 一致で復元される."""
        arrays = make_small_arrays(5)
        objective = ObjectiveState(arrays=arrays, stats=[], total_score=42.5)
        best_arrays = make_small_arrays(5)
        rng = np.random.default_rng(99)
        rng_state = rng.bit_generator.state

        state = SAState(iter=1234, current_score=10.5, best_score=9.0, n_accepted=100, n_total=200)
        ckpt_path = tmp_path / "test.pkl.gz"

        save_checkpoint(
            state=state,
            arrays=arrays,
            objective_state=objective,
            best_arrays=best_arrays,
            best_score=9.0,
            rng_state=rng_state,
            path=ckpt_path,
        )

        loaded_state, _, _, _, loaded_best_score, _ = load_checkpoint(ckpt_path)

        assert loaded_state.iter == 1234
        assert abs(loaded_state.current_score - 10.5) < 1e-9
        assert abs(loaded_state.best_score - 9.0) < 1e-9
        assert loaded_state.n_accepted == 100
        assert loaded_state.n_total == 200
        assert abs(loaded_best_score - 9.0) < 1e-9

    def test_sastate_iter_zero(self, tmp_path: Path) -> None:
        """iter=0 の初期状態も正しく保存・復元できる."""
        arrays = make_small_arrays(3)
        objective = ObjectiveState(arrays=arrays, stats=[], total_score=0.0)
        best_arrays = make_small_arrays(3)
        rng = np.random.default_rng(0)
        rng_state = rng.bit_generator.state
        state = SAState()
        ckpt_path = tmp_path / "zero.pkl.gz"

        save_checkpoint(
            state=state,
            arrays=arrays,
            objective_state=objective,
            best_arrays=best_arrays,
            best_score=0.0,
            rng_state=rng_state,
            path=ckpt_path,
        )

        loaded_state, _, _, _, _, _ = load_checkpoint(ckpt_path)
        assert loaded_state.iter == 0
        assert abs(loaded_state.current_score - 0.0) < 1e-9


# ---------------------------------------------------------------------------
# Cycle 2: PopulationArrays の bitwise 一致
# ---------------------------------------------------------------------------


class TestPopulationArraysRoundTrip:
    """PopulationArrays の save/load bitwise 一致テスト."""

    def test_arrays_bitwise_equal(self, tmp_path: Path) -> None:
        """全配列が bitwise 一致で復元される."""
        arrays = make_small_arrays(20)
        objective = ObjectiveState(arrays=arrays, stats=[], total_score=0.0)
        best_arrays = make_small_arrays(20)
        rng = np.random.default_rng(1)
        rng_state = rng.bit_generator.state
        state = SAState(iter=50, current_score=5.0, best_score=3.0)
        ckpt_path = tmp_path / "arrays.pkl.gz"

        save_checkpoint(
            state=state,
            arrays=arrays,
            objective_state=objective,
            best_arrays=best_arrays,
            best_score=3.0,
            rng_state=rng_state,
            path=ckpt_path,
        )

        _, loaded_arrays, _, loaded_best_arrays, _, _ = load_checkpoint(ckpt_path)

        assert np.array_equal(loaded_arrays.age, arrays.age)
        assert np.array_equal(loaded_arrays.sex, arrays.sex)
        assert np.array_equal(loaded_arrays.role, arrays.role)
        assert np.array_equal(loaded_arrays.household_id, arrays.household_id)
        assert np.array_equal(loaded_arrays.family_type, arrays.family_type)

        assert np.array_equal(loaded_best_arrays.age, best_arrays.age)
        assert np.array_equal(loaded_best_arrays.sex, best_arrays.sex)
        assert np.array_equal(loaded_best_arrays.household_id, best_arrays.household_id)

    def test_arrays_dtype_preserved(self, tmp_path: Path) -> None:
        """配列の dtype が保持される."""
        arrays = make_small_arrays(5)
        objective = ObjectiveState(arrays=arrays, stats=[], total_score=0.0)
        best_arrays = make_small_arrays(5)
        rng = np.random.default_rng(2)
        rng_state = rng.bit_generator.state
        state = SAState()
        ckpt_path = tmp_path / "dtype.pkl.gz"

        save_checkpoint(
            state=state,
            arrays=arrays,
            objective_state=objective,
            best_arrays=best_arrays,
            best_score=0.0,
            rng_state=rng_state,
            path=ckpt_path,
        )

        _, loaded_arrays, _, _, _, _ = load_checkpoint(ckpt_path)

        assert loaded_arrays.age.dtype == np.int16
        assert loaded_arrays.sex.dtype == np.int8
        assert loaded_arrays.role.dtype == np.int8
        assert loaded_arrays.household_id.dtype == np.int32
        assert loaded_arrays.family_type.dtype == np.int8

    def test_couple_arrays_roundtrip(self, tmp_path: Path) -> None:
        """夫婦世帯の配列も正しく復元できる."""
        arrays = make_couple_arrays()
        objective = ObjectiveState(arrays=arrays, stats=[], total_score=0.0)
        best_arrays = make_couple_arrays()
        rng = np.random.default_rng(3)
        rng_state = rng.bit_generator.state
        state = SAState(iter=10, current_score=5.0, best_score=4.0)
        ckpt_path = tmp_path / "couple.pkl.gz"

        save_checkpoint(
            state=state,
            arrays=arrays,
            objective_state=objective,
            best_arrays=best_arrays,
            best_score=4.0,
            rng_state=rng_state,
            path=ckpt_path,
        )

        _, loaded_arrays, _, _, _, _ = load_checkpoint(ckpt_path)
        assert loaded_arrays.n_persons == arrays.n_persons
        assert np.array_equal(loaded_arrays.age, arrays.age)


# ---------------------------------------------------------------------------
# Cycle 3: ObjectiveState の保存・復元
# ---------------------------------------------------------------------------


class TestObjectiveStateRoundTrip:
    """ObjectiveState の save/load テスト."""

    def test_objective_total_score_preserved(self, tmp_path: Path) -> None:
        """total_score が保持される."""
        arrays = make_small_arrays(10)
        from synthpop_jp.io.schemas import AgeDiffCoupleRow, AgeDiffParentChildRow, DemographicByAgeSexRow

        demo_rows = [
            DemographicByAgeSexRow(sex="M", age=30, count=5),
            DemographicByAgeSexRow(sex="M", age=35, count=5),
            DemographicByAgeSexRow(sex="F", age=30, count=0),
            DemographicByAgeSexRow(sex="F", age=35, count=0),
        ]
        objective = ObjectiveState.from_arrays(
            arrays=arrays,
            age_diff_parent_child=[],
            age_diff_couple=[],
            demographic_by_age_sex=demo_rows,
        )
        original_score = objective.total_score

        best_arrays = make_small_arrays(10)
        rng = np.random.default_rng(4)
        rng_state = rng.bit_generator.state
        state = SAState(iter=100, current_score=original_score, best_score=original_score)
        ckpt_path = tmp_path / "objective.pkl.gz"

        save_checkpoint(
            state=state,
            arrays=arrays,
            objective_state=objective,
            best_arrays=best_arrays,
            best_score=original_score,
            rng_state=rng_state,
            path=ckpt_path,
        )

        _, _, loaded_objective, _, _, _ = load_checkpoint(ckpt_path)

        assert abs(loaded_objective.total_score - original_score) < 1e-9

    def test_objective_histograms_preserved(self, tmp_path: Path) -> None:
        """stats の observed/target ヒストグラムが保持される."""
        arrays = make_small_arrays(10)
        from synthpop_jp.io.schemas import DemographicByAgeSexRow

        demo_rows = [
            DemographicByAgeSexRow(sex="M", age=30, count=3),
            DemographicByAgeSexRow(sex="M", age=35, count=2),
            DemographicByAgeSexRow(sex="F", age=30, count=1),
            DemographicByAgeSexRow(sex="F", age=35, count=4),
        ]
        objective = ObjectiveState.from_arrays(
            arrays=arrays,
            age_diff_parent_child=[],
            age_diff_couple=[],
            demographic_by_age_sex=demo_rows,
        )

        best_arrays = make_small_arrays(10)
        rng = np.random.default_rng(5)
        rng_state = rng.bit_generator.state
        state = SAState()
        ckpt_path = tmp_path / "histograms.pkl.gz"

        save_checkpoint(
            state=state,
            arrays=arrays,
            objective_state=objective,
            best_arrays=best_arrays,
            best_score=objective.total_score,
            rng_state=rng_state,
            path=ckpt_path,
        )

        _, _, loaded_objective, _, _, _ = load_checkpoint(ckpt_path)

        assert len(loaded_objective.stats) == len(objective.stats)
        for orig_stat, loaded_stat in zip(objective.stats, loaded_objective.stats, strict=False):
            assert np.array_equal(orig_stat.observed, loaded_stat.observed)
            assert np.array_equal(orig_stat.target, loaded_stat.target)
            assert np.array_equal(orig_stat.bin_edges, loaded_stat.bin_edges)


# ---------------------------------------------------------------------------
# Cycle 4: rng 状態の保存・復元
# ---------------------------------------------------------------------------


class TestRngStateRoundTrip:
    """rng 状態の save/load bitwise 一致テスト."""

    def test_rng_state_next_sample_bitwise_equal(self, tmp_path: Path) -> None:
        """rng 状態を保存・復元後、次の乱数が bitwise 一致する."""
        rng_orig = np.random.default_rng(777)
        # 100 回サンプルして状態を進める
        for _ in range(100):
            _ = rng_orig.uniform()

        rng_state_saved = rng_orig.bit_generator.state

        # 状態を保存して load
        arrays = make_small_arrays(5)
        objective = ObjectiveState(arrays=arrays, stats=[], total_score=0.0)
        best_arrays = make_small_arrays(5)
        state = SAState(iter=100)
        ckpt_path = tmp_path / "rng.pkl.gz"

        save_checkpoint(
            state=state,
            arrays=arrays,
            objective_state=objective,
            best_arrays=best_arrays,
            best_score=0.0,
            rng_state=rng_state_saved,
            path=ckpt_path,
        )

        _, _, _, _, _, loaded_rng_state = load_checkpoint(ckpt_path)

        # 復元した状態から rng を再構築して次の sample を比較
        rng_restored = np.random.default_rng()
        rng_restored.bit_generator.state = loaded_rng_state

        next_sample_orig = rng_orig.uniform()
        next_sample_restored = rng_restored.uniform()

        assert next_sample_orig == next_sample_restored, (
            f"rng 状態復元後の乱数が一致しない: {next_sample_orig} != {next_sample_restored}"
        )

    def test_rng_state_multiple_samples_bitwise_equal(self, tmp_path: Path) -> None:
        """rng 状態復元後、複数の乱数が bitwise 一致する."""
        rng_orig = np.random.default_rng(42)
        for _ in range(50):
            _ = rng_orig.integers(0, 100)

        rng_state_saved = rng_orig.bit_generator.state
        arrays = make_small_arrays(3)
        objective = ObjectiveState(arrays=arrays, stats=[], total_score=0.0)
        best_arrays = make_small_arrays(3)
        state = SAState(iter=50)
        ckpt_path = tmp_path / "rng_multi.pkl.gz"

        save_checkpoint(
            state=state,
            arrays=arrays,
            objective_state=objective,
            best_arrays=best_arrays,
            best_score=0.0,
            rng_state=rng_state_saved,
            path=ckpt_path,
        )

        _, _, _, _, _, loaded_rng_state = load_checkpoint(ckpt_path)
        rng_restored = np.random.default_rng()
        rng_restored.bit_generator.state = loaded_rng_state

        samples_orig = [rng_orig.integers(0, 100) for _ in range(20)]
        samples_restored = [rng_restored.integers(0, 100) for _ in range(20)]

        assert samples_orig == samples_restored


# ---------------------------------------------------------------------------
# Cycle 5: AnnealingConfig の checkpoint フィールド
# ---------------------------------------------------------------------------


class TestAnnealingConfigCheckpoint:
    """AnnealingConfig の checkpoint 関連フィールドのテスト."""

    def test_checkpoint_every_n_iters_default(self) -> None:
        """checkpoint_every_n_iters のデフォルト値が 10000."""
        config = AnnealingConfig()
        assert config.checkpoint_every_n_iters == 10000

    def test_checkpoint_dir_default_none(self) -> None:
        """checkpoint_dir のデフォルト値が None."""
        config = AnnealingConfig()
        assert config.checkpoint_dir is None

    def test_checkpoint_dir_can_be_set(self, tmp_path: Path) -> None:
        """checkpoint_dir に Path を設定できる."""
        config = AnnealingConfig(checkpoint_dir=tmp_path)
        assert config.checkpoint_dir == tmp_path

    def test_checkpoint_every_n_iters_custom(self) -> None:
        """checkpoint_every_n_iters を変更できる."""
        config = AnnealingConfig(checkpoint_every_n_iters=5000)
        assert config.checkpoint_every_n_iters == 5000


# ---------------------------------------------------------------------------
# Cycle 6: SARunner.run の checkpoint フック
# ---------------------------------------------------------------------------


class TestSARunnerCheckpointHook:
    """SARunner.run が checkpoint ファイルを正しく出力するテスト."""

    def _make_simple_run(
        self,
        tmp_path: Path,
        n_iters: int = 100,
        checkpoint_every: int = 50,
    ) -> tuple[SARunner, PopulationArrays, ObjectiveState, AnnealingConfig, ExponentialCooling]:
        """テスト用の SA 実行セットアップを返す."""
        from synthpop_jp.io.schemas import DemographicByAgeSexRow
        from synthpop_jp.optimize.transitions import AgeChangeTransition

        arrays = make_small_arrays(10)
        demo_rows = [
            DemographicByAgeSexRow(sex="M", age=25, count=5),
            DemographicByAgeSexRow(sex="M", age=30, count=5),
            DemographicByAgeSexRow(sex="F", age=25, count=0),
            DemographicByAgeSexRow(sex="F", age=30, count=0),
        ]
        objective = ObjectiveState.from_arrays(
            arrays=arrays,
            age_diff_parent_child=[],
            age_diff_couple=[],
            demographic_by_age_sex=demo_rows,
        )
        config = AnnealingConfig(
            T0=100.0,
            alpha=0.99,
            max_iters=n_iters,
            evals_per_agent=0,
            checkpoint_every_n_iters=checkpoint_every,
            checkpoint_dir=tmp_path / "checkpoints",
        )
        cooling = ExponentialCooling(T0=config.T0, alpha=config.alpha)
        rng = np.random.default_rng(1)
        runner = SARunner(rng=rng)
        return runner, arrays, objective, config, cooling

    def test_checkpoint_files_created(self, tmp_path: Path) -> None:
        """checkpoint_every_n_iters ごとに .pkl.gz ファイルが生成される."""
        from synthpop_jp.io.schemas import DemographicByAgeSexRow
        from synthpop_jp.optimize.transitions import AgeChangeTransition

        arrays = make_small_arrays(10)
        demo_rows = [
            DemographicByAgeSexRow(sex="M", age=25, count=5),
            DemographicByAgeSexRow(sex="M", age=30, count=5),
            DemographicByAgeSexRow(sex="F", age=25, count=0),
            DemographicByAgeSexRow(sex="F", age=30, count=0),
        ]
        objective = ObjectiveState.from_arrays(
            arrays=arrays,
            age_diff_parent_child=[],
            age_diff_couple=[],
            demographic_by_age_sex=demo_rows,
        )
        transition = AgeChangeTransition(
            arrays=arrays,
            demo_by_age_sex=demo_rows,
            rng=np.random.default_rng(2),
        )
        checkpoint_dir = tmp_path / "checkpoints"
        config = AnnealingConfig(
            T0=100.0,
            alpha=0.99,
            max_iters=200,
            evals_per_agent=0,
            log_every_n_iters=50,
            trace_enabled=False,
            checkpoint_every_n_iters=100,
            checkpoint_dir=checkpoint_dir,
        )
        cooling = ExponentialCooling(T0=config.T0, alpha=config.alpha)
        runner = SARunner(rng=np.random.default_rng(1))

        runner.run(
            arrays=arrays,
            objective=objective,
            transition=transition,
            cooling=cooling,
            config=config,
            progress_enabled=False,
        )

        # iter_100.pkl.gz と latest.pkl.gz が生成されること
        assert (checkpoint_dir / "iter_100.pkl.gz").exists(), "iter_100.pkl.gz が存在しない"
        assert (checkpoint_dir / "latest.pkl.gz").exists(), "latest.pkl.gz が存在しない"

    def test_latest_equals_last_checkpoint(self, tmp_path: Path) -> None:
        """latest.pkl.gz の内容が最後の checkpoint と一致する."""
        from synthpop_jp.io.schemas import DemographicByAgeSexRow
        from synthpop_jp.optimize.transitions import AgeChangeTransition

        arrays = make_small_arrays(10)
        demo_rows = [
            DemographicByAgeSexRow(sex="M", age=25, count=5),
            DemographicByAgeSexRow(sex="M", age=30, count=5),
            DemographicByAgeSexRow(sex="F", age=25, count=0),
            DemographicByAgeSexRow(sex="F", age=30, count=0),
        ]
        objective = ObjectiveState.from_arrays(
            arrays=arrays,
            age_diff_parent_child=[],
            age_diff_couple=[],
            demographic_by_age_sex=demo_rows,
        )
        transition = AgeChangeTransition(
            arrays=arrays,
            demo_by_age_sex=demo_rows,
            rng=np.random.default_rng(3),
        )
        checkpoint_dir = tmp_path / "checkpoints"
        config = AnnealingConfig(
            T0=100.0,
            alpha=0.99,
            max_iters=150,
            evals_per_agent=0,
            trace_enabled=False,
            checkpoint_every_n_iters=100,
            checkpoint_dir=checkpoint_dir,
        )
        cooling = ExponentialCooling(T0=config.T0, alpha=config.alpha)
        runner = SARunner(rng=np.random.default_rng(4))

        runner.run(
            arrays=arrays,
            objective=objective,
            transition=transition,
            cooling=cooling,
            config=config,
            progress_enabled=False,
        )

        # latest と iter_100 の best_score が同一
        latest_state, _, _, _, latest_best_score, _ = load_checkpoint(
            checkpoint_dir / "latest.pkl.gz"
        )
        iter_state, _, _, _, iter_best_score, _ = load_checkpoint(
            checkpoint_dir / "iter_100.pkl.gz"
        )
        assert latest_state.iter == iter_state.iter
        assert abs(latest_best_score - iter_best_score) < 1e-9


# ---------------------------------------------------------------------------
# Cycle 7: SARunner.run の resume
# ---------------------------------------------------------------------------


class TestSARunnerResume:
    """SARunner.run の resume_from 引数のテスト."""

    def test_resume_continues_iter_count(self, tmp_path: Path) -> None:
        """resume 後の反復数が連続している（checkpoint iter + 追加反復）."""
        from synthpop_jp.io.schemas import DemographicByAgeSexRow
        from synthpop_jp.optimize.transitions import AgeChangeTransition

        arrays = make_small_arrays(10)
        demo_rows = [
            DemographicByAgeSexRow(sex="M", age=25, count=5),
            DemographicByAgeSexRow(sex="M", age=30, count=5),
            DemographicByAgeSexRow(sex="F", age=25, count=0),
            DemographicByAgeSexRow(sex="F", age=30, count=0),
        ]
        objective = ObjectiveState.from_arrays(
            arrays=arrays,
            age_diff_parent_child=[],
            age_diff_couple=[],
            demographic_by_age_sex=demo_rows,
        )
        transition = AgeChangeTransition(
            arrays=arrays,
            demo_by_age_sex=demo_rows,
            rng=np.random.default_rng(10),
        )
        checkpoint_dir = tmp_path / "checkpoints"
        config_phase1 = AnnealingConfig(
            T0=100.0,
            alpha=0.99,
            max_iters=200,
            evals_per_agent=0,
            trace_enabled=False,
            checkpoint_every_n_iters=200,
            checkpoint_dir=checkpoint_dir,
        )
        cooling = ExponentialCooling(T0=config_phase1.T0, alpha=config_phase1.alpha)
        runner = SARunner(rng=np.random.default_rng(5))

        result_phase1 = runner.run(
            arrays=arrays,
            objective=objective,
            transition=transition,
            cooling=cooling,
            config=config_phase1,
            progress_enabled=False,
        )

        checkpoint_path = checkpoint_dir / "latest.pkl.gz"
        assert checkpoint_path.exists()

        # phase 2: checkpoint から resume して追加 100 反復
        arrays2 = make_small_arrays(10)
        demo_rows2 = demo_rows[:]
        objective2 = ObjectiveState.from_arrays(
            arrays=arrays2,
            age_diff_parent_child=[],
            age_diff_couple=[],
            demographic_by_age_sex=demo_rows2,
        )
        transition2 = AgeChangeTransition(
            arrays=arrays2,
            demo_by_age_sex=demo_rows2,
            rng=np.random.default_rng(11),
        )
        config_phase2 = AnnealingConfig(
            T0=100.0,
            alpha=0.99,
            max_iters=300,
            evals_per_agent=0,
            trace_enabled=False,
            checkpoint_every_n_iters=0,
            checkpoint_dir=None,
        )
        cooling2 = ExponentialCooling(T0=config_phase2.T0, alpha=config_phase2.alpha)
        runner2 = SARunner(rng=np.random.default_rng(6))

        result_phase2 = runner2.run(
            arrays=arrays2,
            objective=objective2,
            transition=transition2,
            cooling=cooling2,
            config=config_phase2,
            resume_from=checkpoint_path,
            progress_enabled=False,
        )

        # resume 後の最終 iter が checkpoint の iter + 追加分
        assert result_phase2.final_state.iter > result_phase1.final_state.iter


# ---------------------------------------------------------------------------
# Cycle 8: bitwise 一致 regression test
# ---------------------------------------------------------------------------


class TestBitwiseEqualityRegression:
    """baseline vs split run の bitwise 一致 regression test."""

    def test_split_run_bitwise_equal_to_baseline(self, tmp_path: Path) -> None:
        """SA 1000 反復 baseline == 500 反復 checkpoint + resume 500 反復.

        best_score と best_arrays.age が bitwise 一致することを確認する。
        """
        from synthpop_jp.io.schemas import DemographicByAgeSexRow
        from synthpop_jp.optimize.transitions import AgeChangeTransition

        demo_rows = [
            DemographicByAgeSexRow(sex="M", age=25, count=3),
            DemographicByAgeSexRow(sex="M", age=30, count=2),
            DemographicByAgeSexRow(sex="M", age=35, count=5),
            DemographicByAgeSexRow(sex="F", age=25, count=2),
            DemographicByAgeSexRow(sex="F", age=30, count=3),
            DemographicByAgeSexRow(sex="F", age=35, count=2),
        ]

        seed = 42

        # ---- baseline: 1000 反復 ----
        arrays_base = make_small_arrays(12)
        objective_base = ObjectiveState.from_arrays(
            arrays=arrays_base,
            age_diff_parent_child=[],
            age_diff_couple=[],
            demographic_by_age_sex=demo_rows,
        )
        transition_base = AgeChangeTransition(
            arrays=arrays_base,
            demo_by_age_sex=demo_rows,
            rng=np.random.default_rng(seed + 1),
        )
        config_base = AnnealingConfig(
            T0=100.0,
            alpha=0.999,
            max_iters=1000,
            evals_per_agent=0,
            trace_enabled=False,
            checkpoint_every_n_iters=0,
            checkpoint_dir=None,
        )
        cooling_base = ExponentialCooling(T0=config_base.T0, alpha=config_base.alpha)
        runner_base = SARunner(rng=np.random.default_rng(seed))

        result_base = runner_base.run(
            arrays=arrays_base,
            objective=objective_base,
            transition=transition_base,
            cooling=cooling_base,
            config=config_base,
            progress_enabled=False,
        )

        # ---- phase 1: 500 反復 + checkpoint ----
        checkpoint_dir = tmp_path / "ckpt"
        arrays_p1 = make_small_arrays(12)
        objective_p1 = ObjectiveState.from_arrays(
            arrays=arrays_p1,
            age_diff_parent_child=[],
            age_diff_couple=[],
            demographic_by_age_sex=demo_rows,
        )
        transition_p1 = AgeChangeTransition(
            arrays=arrays_p1,
            demo_by_age_sex=demo_rows,
            rng=np.random.default_rng(seed + 1),
        )
        config_p1 = AnnealingConfig(
            T0=100.0,
            alpha=0.999,
            max_iters=500,
            evals_per_agent=0,
            trace_enabled=False,
            checkpoint_every_n_iters=500,
            checkpoint_dir=checkpoint_dir,
        )
        cooling_p1 = ExponentialCooling(T0=config_p1.T0, alpha=config_p1.alpha)
        runner_p1 = SARunner(rng=np.random.default_rng(seed))

        runner_p1.run(
            arrays=arrays_p1,
            objective=objective_p1,
            transition=transition_p1,
            cooling=cooling_p1,
            config=config_p1,
            progress_enabled=False,
        )

        checkpoint_path = checkpoint_dir / "latest.pkl.gz"
        assert checkpoint_path.exists(), "checkpoint が生成されていない"

        # ---- phase 2: resume して 500 反復追加 ----
        arrays_p2 = make_small_arrays(12)
        objective_p2 = ObjectiveState.from_arrays(
            arrays=arrays_p2,
            age_diff_parent_child=[],
            age_diff_couple=[],
            demographic_by_age_sex=demo_rows,
        )
        transition_p2 = AgeChangeTransition(
            arrays=arrays_p2,
            demo_by_age_sex=demo_rows,
            rng=np.random.default_rng(seed + 1),
        )
        config_p2 = AnnealingConfig(
            T0=100.0,
            alpha=0.999,
            max_iters=1000,
            evals_per_agent=0,
            trace_enabled=False,
            checkpoint_every_n_iters=0,
            checkpoint_dir=None,
        )
        cooling_p2 = ExponentialCooling(T0=config_p2.T0, alpha=config_p2.alpha)
        runner_p2 = SARunner(rng=np.random.default_rng(seed + 99))  # rng は resume_from で上書き

        result_split = runner_p2.run(
            arrays=arrays_p2,
            objective=objective_p2,
            transition=transition_p2,
            cooling=cooling_p2,
            config=config_p2,
            resume_from=checkpoint_path,
            progress_enabled=False,
        )

        # best_score が bitwise 一致
        assert result_split.final_state.best_score == result_base.final_state.best_score, (
            f"best_score が一致しない: "
            f"split={result_split.final_state.best_score}, "
            f"base={result_base.final_state.best_score}"
        )

        # best_arrays.age が bitwise 一致
        assert np.array_equal(result_split.best_arrays.age, result_base.best_arrays.age), (
            "best_arrays.age が一致しない"
        )

        # iter が一致
        assert result_split.final_state.iter == result_base.final_state.iter, (
            f"最終 iter が一致しない: "
            f"split={result_split.final_state.iter}, "
            f"base={result_base.final_state.iter}"
        )


# ---------------------------------------------------------------------------
# Cycle 9: 性能 skeleton
# ---------------------------------------------------------------------------


class TestCheckpointPerformance:
    """checkpoint save が 100ms 以内であることの skeleton テスト."""

    def test_checkpoint_save_under_100ms(self, tmp_path: Path) -> None:
        """1000 世帯規模で checkpoint save が 100ms 以内（I/O 含む）.

        実際の 1000 世帯は 3000 人程度。ここでは 1000 人でテスト。
        """
        from synthpop_jp.io.schemas import DemographicByAgeSexRow

        arrays = make_small_arrays(1000)
        demo_rows = [
            DemographicByAgeSexRow(sex="M", age=age, count=20)
            for age in range(0, 100, 5)
        ] + [
            DemographicByAgeSexRow(sex="F", age=age, count=20)
            for age in range(0, 100, 5)
        ]
        objective = ObjectiveState.from_arrays(
            arrays=arrays,
            age_diff_parent_child=[],
            age_diff_couple=[],
            demographic_by_age_sex=demo_rows,
        )
        best_arrays = make_small_arrays(1000)
        rng = np.random.default_rng(42)
        rng_state = rng.bit_generator.state
        state = SAState(iter=10000, current_score=50.0, best_score=40.0)
        ckpt_path = tmp_path / "perf.pkl.gz"

        start = time.monotonic()
        save_checkpoint(
            state=state,
            arrays=arrays,
            objective_state=objective,
            best_arrays=best_arrays,
            best_score=40.0,
            rng_state=rng_state,
            path=ckpt_path,
        )
        elapsed = time.monotonic() - start

        assert elapsed < 0.1, f"checkpoint save が 100ms を超えた: {elapsed * 1000:.1f}ms"
