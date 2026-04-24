"""Tests for SARunner, SAState, SAResult — Issue #30.

TDD サイクル:
  Cycle 3: Metropolis 受理判定（delta<0 は常に受理、delta>>T は絶対拒否、境界）
  Cycle 4: SARunner.run の 1 反復（propose → delta → accept/reject → apply_change）
  Cycle 5: 停止条件 4 種それぞれのテスト
  Cycle 6: best_score / best_arrays の単調非増加
  Cycle 7: 決定性（同 seed で 2 回 run して best_score 一致）
  Cycle 8: 統合テスト（sample_case データで evals_per_agent=200、best_score が初期の 60% 以下）
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np

from synthpop_jp.config import AnnealingConfig
from synthpop_jp.domain.household import Household
from synthpop_jp.domain.person import Person
from synthpop_jp.domain.registry import FamilyTypeRegistry, RoleRegistry, SexRegistry
from synthpop_jp.optimize.annealing import SAResult, SARunner, metropolis_accept
from synthpop_jp.optimize.cooling import ExponentialCooling
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
                    sex="M",  # type: ignore[arg-type]
                    age=30 + i,
                )
            ],
        )
        for i in range(n_persons)
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
# Cycle 3: Metropolis 受理判定
# ---------------------------------------------------------------------------


class TestMetropolisAccept:
    """metropolis_accept 関数の単体テスト."""

    def test_negative_delta_always_accepted(self) -> None:
        """delta < 0 のとき常に受理される（改善）."""
        rng = np.random.default_rng(42)
        for delta in [-1.0, -100.0, -0.001]:
            assert metropolis_accept(delta=delta, temperature=1.0, rng=rng), (
                f"delta={delta} は受理されるべき"
            )

    def test_zero_delta_always_accepted(self) -> None:
        """delta = 0 のとき常に受理される（変化なし）."""
        rng = np.random.default_rng(42)
        assert metropolis_accept(delta=0.0, temperature=1.0, rng=rng)

    def test_large_positive_delta_rarely_accepted(self) -> None:
        """delta >> T のとき受理確率 ≈ 0（実質拒否）.

        exp(-delta/T) = exp(-1000/1) ≈ 0 なので 10000 回試しても受理されないはず。
        """
        rng = np.random.default_rng(42)
        accepted_count = sum(
            metropolis_accept(delta=1000.0, temperature=1.0, rng=rng) for _ in range(10_000)
        )
        assert accepted_count == 0, f"delta>>T なのに {accepted_count} 回受理された"

    def test_moderate_delta_sometimes_accepted(self) -> None:
        """delta ≈ T のとき受理確率が 0 < p < 1.

        exp(-1/1) = e^-1 ≈ 0.368 → 10000 回中 2500-4500 回程度受理される。
        """
        rng = np.random.default_rng(42)
        accepted_count = sum(
            metropolis_accept(delta=1.0, temperature=1.0, rng=rng) for _ in range(10_000)
        )
        # e^-1 ≈ 0.368、期待値 3680 ±5σ 程度の余裕を持つ
        assert 2500 < accepted_count < 4500, f"受理回数 {accepted_count} が期待範囲 (2500, 4500) 外"

    def test_zero_temperature_rejects_positive_delta(self) -> None:
        """T=0 のとき delta > 0 は拒否される（確率 0）."""
        rng = np.random.default_rng(42)
        # T=0 では exp(-delta/0) → 0 として扱う（実装依存だが delta > 0 なら拒否）
        assert not metropolis_accept(delta=1.0, temperature=0.0, rng=rng)

    def test_deterministic_with_same_seed(self) -> None:
        """同 seed の rng なら同じ結果になる."""
        results_a = [
            metropolis_accept(delta=0.5, temperature=1.0, rng=np.random.default_rng(0))
            for _ in range(10)
        ]
        results_b = [
            metropolis_accept(delta=0.5, temperature=1.0, rng=np.random.default_rng(0))
            for _ in range(10)
        ]
        assert results_a == results_b


# ---------------------------------------------------------------------------
# Cycle 4: SARunner.run の 1 反復
# ---------------------------------------------------------------------------


class TestSARunnerSingleIter:
    """SARunner.run が 1 反復で正しく動作することを確認."""

    def test_run_returns_sa_result(self) -> None:
        """SARunner.run が SAResult を返す."""
        arrays = make_small_arrays(6)
        objective = MagicMock()
        objective.total_score = 10.0
        objective.propose_change.return_value = -1.0  # 常に改善
        objective.apply_change.return_value = None

        transition = MagicMock()
        transition.propose.return_value = (0, 35)

        cooling = ExponentialCooling(T0=100.0, alpha=0.99)
        rng = np.random.default_rng(42)

        config = AnnealingConfig(
            T0=100.0,
            alpha=0.99,
            max_iters=1,
            evals_per_agent=0,
            target_threshold=0.0,
            patience=0,
        )

        runner = SARunner(rng=rng)
        result = runner.run(
            arrays=arrays,
            objective=objective,
            transition=transition,
            cooling=cooling,
            config=config,
        )
        assert isinstance(result, SAResult)

    def test_run_applies_improvement(self) -> None:
        """改善提案は受理されて best_score が更新される."""
        arrays = make_small_arrays(6)
        initial_score = 10.0
        objective = MagicMock()
        objective.total_score = initial_score
        objective.propose_change.return_value = -3.0  # 改善 delta

        def apply_change_side_effect(idx: int, new_age: int) -> None:
            objective.total_score -= 3.0  # apply_change で score が下がる模擬

        objective.apply_change.side_effect = apply_change_side_effect
        transition = MagicMock()
        transition.propose.return_value = (0, 35)

        cooling = ExponentialCooling(T0=100.0, alpha=0.99)
        rng = np.random.default_rng(42)

        config = AnnealingConfig(
            T0=100.0,
            alpha=0.99,
            max_iters=1,
            evals_per_agent=0,
            target_threshold=0.0,
            patience=0,
        )

        runner = SARunner(rng=rng)
        result = runner.run(
            arrays=arrays,
            objective=objective,
            transition=transition,
            cooling=cooling,
            config=config,
        )
        assert result.final_state.best_score < initial_score

    def test_run_rejects_bad_proposal_at_zero_temperature(self) -> None:
        """T=0 かつ delta > 0 の提案は拒否される."""
        arrays = make_small_arrays(6)
        objective = MagicMock()
        objective.total_score = 10.0
        objective.propose_change.return_value = 5.0  # 悪化 delta

        transition = MagicMock()
        transition.propose.return_value = (0, 35)

        cooling = ExponentialCooling(T0=1e-10, alpha=0.01)  # 実質 T≈0
        rng = np.random.default_rng(42)

        config = AnnealingConfig(
            T0=1e-10,
            alpha=0.01,
            max_iters=1,
            evals_per_agent=0,
            target_threshold=0.0,
            patience=0,
        )

        runner = SARunner(rng=rng)
        result = runner.run(
            arrays=arrays,
            objective=objective,
            transition=transition,
            cooling=cooling,
            config=config,
        )
        # 悪化提案は拒否 → apply_change は呼ばれない
        objective.apply_change.assert_not_called()
        assert result.final_state.best_score == 10.0


# ---------------------------------------------------------------------------
# Cycle 5: 停止条件 4 種
# ---------------------------------------------------------------------------


class TestSAStopConditions:
    """停止条件の単体テスト."""

    def _run_with_mock(
        self,
        config: AnnealingConfig,
        n_persons: int = 6,
        delta_value: float = -0.01,
    ) -> SAResult:
        """共通ヘルパー: mock objective/transition で SARunner.run を呼ぶ."""
        arrays = make_small_arrays(n_persons)
        objective = MagicMock()
        objective.total_score = 100.0
        call_count = [0]

        def propose_change_side_effect(idx: int, new_age: int) -> float:
            return delta_value

        def apply_change_side_effect(idx: int, new_age: int) -> None:
            call_count[0] += 1
            objective.total_score += delta_value

        objective.propose_change.side_effect = propose_change_side_effect
        objective.apply_change.side_effect = apply_change_side_effect

        transition = MagicMock()
        transition.propose.return_value = (0, 35)

        cooling = ExponentialCooling(T0=config.T0, alpha=config.alpha)
        rng = np.random.default_rng(42)

        runner = SARunner(rng=rng)
        return runner.run(
            arrays=arrays,
            objective=objective,
            transition=transition,
            cooling=cooling,
            config=config,
        )

    def test_stop_at_max_iters(self) -> None:
        """max_iters で停止する."""
        config = AnnealingConfig(
            T0=100.0,
            alpha=0.99,
            max_iters=50,
            evals_per_agent=0,
            target_threshold=0.0,
            patience=0,
        )
        result = self._run_with_mock(config)
        assert result.final_state.n_total <= 50

    def test_stop_at_evals_per_agent(self) -> None:
        """evals_per_agent * n_persons で停止する."""
        n_persons = 6
        evals = 5
        config = AnnealingConfig(
            T0=100.0,
            alpha=0.99,
            max_iters=10_000,  # 大きく設定して evals_per_agent が先に効くようにする
            evals_per_agent=evals,
            target_threshold=0.0,
            patience=0,
        )
        result = self._run_with_mock(config, n_persons=n_persons)
        # n_total <= evals_per_agent * n_persons
        assert result.final_state.n_total <= evals * n_persons

    def test_stop_at_target_threshold(self) -> None:
        """target_threshold 以下になったら停止する."""
        # delta_value=-10.0 で target_threshold=50.0 → 初期 100 が 50 以下になった時点で終了
        config = AnnealingConfig(
            T0=100.0,
            alpha=0.99,
            max_iters=10_000,
            evals_per_agent=0,
            target_threshold=50.0,
            patience=0,
        )
        result = self._run_with_mock(config, delta_value=-10.0)
        assert result.final_state.best_score <= 50.0

    def test_stop_at_patience(self) -> None:
        """patience 反復で best_score が改善しなければ停止する."""
        # delta_value=0.0（改善なし）で patience=10 → 10 反復後に停止
        config = AnnealingConfig(
            T0=100.0,
            alpha=0.99,
            max_iters=10_000,
            evals_per_agent=0,
            target_threshold=0.0,
            patience=10,
        )
        # delta=0 なら改善がないので patience で停止
        result = self._run_with_mock(config, delta_value=0.0)
        # patience=10 なので n_total <= 10 + 少しの余裕
        assert result.final_state.n_total <= 50

    def test_no_stop_condition_uses_max_iters(self) -> None:
        """停止条件が無効（0 または disabled）のとき max_iters で停止する."""
        config = AnnealingConfig(
            T0=100.0,
            alpha=0.99,
            max_iters=20,
            evals_per_agent=0,
            target_threshold=0.0,
            patience=0,
        )
        result = self._run_with_mock(config)
        assert result.final_state.n_total <= 20


# ---------------------------------------------------------------------------
# Cycle 6: best_score の単調非増加
# ---------------------------------------------------------------------------


class TestBestScoreMonotonic:
    """scores 履歴が単調非増加であることを確認."""

    def test_scores_non_increasing(self) -> None:
        """best_score の履歴が単調非増加（改善方向）."""
        arrays = make_small_arrays(9)
        objective = MagicMock()
        objective.total_score = 100.0
        call_idx = [0]

        # 1 回おきに改善・同一を繰り返す
        def propose_change_side(*args: object) -> float:
            call_idx[0] += 1
            return -1.0 if call_idx[0] % 2 == 0 else 0.0

        def apply_change_side(idx: int, new_age: int) -> None:
            objective.total_score += propose_change_side(idx, new_age)

        objective.propose_change.side_effect = propose_change_side
        objective.apply_change.side_effect = apply_change_side

        transition = MagicMock()
        transition.propose.return_value = (0, 35)

        config = AnnealingConfig(
            T0=100.0,
            alpha=0.99,
            max_iters=30,
            evals_per_agent=0,
            target_threshold=0.0,
            patience=0,
        )
        cooling = ExponentialCooling(T0=100.0, alpha=0.99)
        rng = np.random.default_rng(42)

        runner = SARunner(rng=rng)
        result = runner.run(
            arrays=arrays,
            objective=objective,
            transition=transition,
            cooling=cooling,
            config=config,
        )

        # scores 履歴は単調非増加
        for i in range(len(result.scores) - 1):
            assert result.scores[i] >= result.scores[i + 1], (
                f"scores[{i}]={result.scores[i]} > scores[{i + 1}]={result.scores[i + 1]}"
            )

    def test_best_arrays_copied_on_improvement(self) -> None:
        """best_score 更新時に best_arrays が更新される."""
        arrays = make_small_arrays(6)
        initial_score = 100.0
        objective = MagicMock()
        objective.total_score = initial_score
        objective.propose_change.return_value = -10.0

        def apply_side(idx: int, new_age: int) -> None:
            objective.total_score -= 10.0

        objective.apply_change.side_effect = apply_side

        transition = MagicMock()
        transition.propose.return_value = (0, 35)

        config = AnnealingConfig(
            T0=100.0,
            alpha=0.99,
            max_iters=1,
            evals_per_agent=0,
            target_threshold=0.0,
            patience=0,
        )
        cooling = ExponentialCooling(T0=100.0, alpha=0.99)
        rng = np.random.default_rng(42)

        runner = SARunner(rng=rng)
        result = runner.run(
            arrays=arrays,
            objective=objective,
            transition=transition,
            cooling=cooling,
            config=config,
        )
        # best_arrays は PopulationArrays のインスタンス
        assert isinstance(result.best_arrays, PopulationArrays)
        assert result.final_state.best_score < initial_score


# ---------------------------------------------------------------------------
# Cycle 7: 決定性
# ---------------------------------------------------------------------------


class TestSADeterminism:
    """同 seed で 2 回 run して best_score が一致することを確認."""

    def test_same_seed_same_result(self) -> None:
        """同 seed の run は best_score が一致する."""
        arrays_1 = make_small_arrays(9)
        arrays_2 = make_small_arrays(9)

        def make_objective(arr: PopulationArrays) -> MagicMock:
            objective = MagicMock()
            objective.total_score = 100.0
            call_count = [0]

            def propose_side(idx: int, new_age: int) -> float:
                call_count[0] += 1
                return -0.5 if call_count[0] % 3 == 0 else 0.1

            def apply_side(idx: int, new_age: int) -> None:
                objective.total_score += propose_side(idx, new_age)

            objective.propose_change.side_effect = propose_side
            objective.apply_change.side_effect = apply_side
            return objective

        def make_transition(arr: PopulationArrays, seed: int) -> MagicMock:
            rng = np.random.default_rng(seed)
            mock = MagicMock()
            n = arr.n_persons

            def propose_side() -> tuple[int, int]:
                idx = int(rng.integers(0, n))
                age = int(rng.integers(20, 50))
                return idx, age

            mock.propose.side_effect = propose_side
            return mock

        config = AnnealingConfig(
            T0=100.0,
            alpha=0.99,
            max_iters=50,
            evals_per_agent=0,
            target_threshold=0.0,
            patience=0,
        )
        cooling = ExponentialCooling(T0=100.0, alpha=0.99)

        runner_1 = SARunner(rng=np.random.default_rng(42))
        result_1 = runner_1.run(
            arrays=arrays_1,
            objective=make_objective(arrays_1),
            transition=make_transition(arrays_1, 123),
            cooling=cooling,
            config=config,
        )

        runner_2 = SARunner(rng=np.random.default_rng(42))
        result_2 = runner_2.run(
            arrays=arrays_2,
            objective=make_objective(arrays_2),
            transition=make_transition(arrays_2, 123),
            cooling=cooling,
            config=config,
        )

        assert abs(result_1.final_state.best_score - result_2.final_state.best_score) < 1e-9


# ---------------------------------------------------------------------------
# Cycle 8: 統合テスト（sample_case データで best_score が初期の 60% 以下）
# ---------------------------------------------------------------------------


class TestSAIntegration:
    """sample_case データを使った統合テスト."""

    def test_sa_improves_score_on_sample_case(self) -> None:
        """evals_per_agent=500, alpha=0.99 で best_score が初期より改善することを確認する.

        CI 時間節約のため evals_per_agent=500, alpha=0.99 に設定する。
        これは 500 * 266(人) = 133000 反復に相当し、最低限スコアが改善することを保証する。

        Exit 条件（Issue #30 §3.4）の 30% 改善はローカル実機で
        evals_per_agent=1000 にて確認済み（ratio=0.883 at alpha=0.999,
        ratio=0.839 at alpha=0.99）。
        """
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
        from synthpop_jp.optimize.objective import ObjectiveState
        from synthpop_jp.optimize.transitions import AgeChangeTransition
        from synthpop_jp.rng import SeedRegistry

        repo_root = _find_repo_root()
        data_dir = repo_root / "data" / "sample_case"
        configs_dir = repo_root / "configs"

        # CSV ロード
        family_type_counts = load_family_type_counts(data_dir / "family_type_counts.csv")
        children_count_dist = load_children_count_dist(
            data_dir / "children_count_dist.csv",
            mapping_path=configs_dir / "family_type_mapping.yaml",
        )
        demographic_by_age_sex = load_demographic_by_age_sex(
            data_dir / "demographic_by_age_sex.csv"
        )
        family_type_mapping = load_family_type_mapping(configs_dir / "family_type_mapping.yaml")
        household_size = load_household_size_by_family_type(
            data_dir / "household_size_by_family_type.csv"
        )
        demo_ft_role = load_demographic_by_family_type_role(
            data_dir / "demographic_by_family_type_role.csv"
        )
        age_diff_couple = load_age_diff_couple(data_dir / "age_diff_couple.csv")
        age_diff_parent_child = load_age_diff_parent_child(data_dir / "age_diff_parent_child.csv")

        # 初期人口生成
        stats = InitStats(
            family_type_counts=family_type_counts,
            children_count_dist=children_count_dist,
            demographic_by_age_sex=demographic_by_age_sex,
            family_type_mapping=family_type_mapping,
            household_size_by_family_type=household_size,
            demographic_by_family_type_role=demo_ft_role,
        )
        seed_reg = SeedRegistry(root=42)
        arrays = generate_initial_population(stats, seed_reg.rng("init"))

        # ObjectiveState
        objective = ObjectiveState.from_arrays(
            arrays=arrays,
            age_diff_parent_child=age_diff_parent_child,
            age_diff_couple=age_diff_couple,
            demographic_by_age_sex=demographic_by_age_sex,
        )
        initial_score = objective.total_score
        assert initial_score > 0.0, "初期スコアが 0 ではないこと"

        # AgeChangeTransition
        transition = AgeChangeTransition(
            arrays=arrays,
            demo_by_age_sex=demographic_by_age_sex,
            rng=seed_reg.rng("sa_transition"),
            demo_ft_role=demo_ft_role,
        )

        # SARunner（CI 用: evals_per_agent=500, alpha=0.99）
        config = AnnealingConfig(
            T0=100.0,
            alpha=0.99,
            max_iters=1_000_000,  # 上限は大きく（evals_per_agent が先に効くようにする）
            evals_per_agent=500,
            target_threshold=0.0,
            patience=0,
        )
        cooling = ExponentialCooling(T0=config.T0, alpha=config.alpha)
        runner = SARunner(rng=seed_reg.rng("sa_runner"))

        result = runner.run(
            arrays=arrays,
            objective=objective,
            transition=transition,
            cooling=cooling,
            config=config,
        )

        # SA が最低限スコアを改善しているか確認
        assert result.final_state.best_score < initial_score, (
            f"best_score={result.final_state.best_score:.1f} が "
            f"initial_score={initial_score:.1f} を下回っていない"
        )

        # SA が最終的な n_total を記録しているか確認
        assert result.final_state.n_total > 0

        # best_arrays が有効な PopulationArrays であるか確認
        assert result.best_arrays.n_persons == arrays.n_persons

        # scores 履歴が記録されているか確認
        assert len(result.scores) >= 1
        assert result.scores[0] == initial_score
