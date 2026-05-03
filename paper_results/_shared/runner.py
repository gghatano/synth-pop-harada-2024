"""Common SA runner for paper_results experiments (Issue #115 Step 2).

実験 1（age-change vs age-swap）と実験 2（hybrid 戦略）の双方が呼ぶ共通の
ラッパ。data/sample_case/ を整数倍スケールしたダミー入力を `tempdir` に作り、
strict_extended (Murata 式(3) 準拠の 21 統計) で目的関数を組み、固定 seed で
SA を 1 回回して `best_score` と統計別 L1 を返す。

`run_one(seed, transition_kind, evals_per_agent, n_households)` は決定論的
（spec §19.3, `uv sync --frozen` 環境）。
"""

from __future__ import annotations

import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

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
from synthpop_jp.optimize.annealing import SARunner
from synthpop_jp.optimize.cooling import ExponentialCooling
from synthpop_jp.optimize.objective import ObjectiveState
from synthpop_jp.optimize.transitions import (
    AgeChangeTransition,
    AgeSwapTransition,
    HybridTransition,
)
from synthpop_jp.rng import SeedRegistry

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_CASE_DIR = REPO_ROOT / "data" / "sample_case"
CONFIGS_DIR = REPO_ROOT / "configs"
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

#: 実験 1 / 2 で使う冷却スケジュールの初期温度（spec §15.1 既定）。
DEFAULT_T0 = 1.0
#: 冷却率（既存実験 9-family-types-coverage と揃える）。
DEFAULT_ALPHA = 0.999
#: HybridTransition の p_change（後半 age-swap 厚めの線形スケジュール）。
HYBRID_P_CHANGE_START = 0.8
HYBRID_P_CHANGE_END = 0.2


@dataclass(frozen=True)
class RunResult:
    """1 回の SA run の結果.

    Attributes
    ----------
    seed : int
        SeedRegistry の root seed。
    transition_kind : str
        ``"age_change"`` / ``"age_swap"`` / ``"hybrid"``。
    n_households : int
        入力世帯数。
    evals_per_agent : int
        SA の停止条件として渡した値（max_iters は ``evals_per_agent * n_persons``）。
    best_score : float
        SA 終了時点での best_score（21 統計の L1 合計）。
    stat_l1 : dict[str, float]
        21 統計別 L1（``stats[i]`` を ``"stat_{i}"`` 形式の key で）。
    elapsed_seconds : float
        SA 実行に要した秒数（壁時計）。
    """

    seed: int
    transition_kind: str
    n_households: int
    evals_per_agent: int
    best_score: float
    stat_l1: dict[str, float]
    elapsed_seconds: float


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _scale_sample_case(target_n_households: int, target_dir: Path) -> None:
    """data/sample_case/ を整数倍スケールして target_dir に書き出す.

    実験 9-family-types-coverage と挙動を揃えるため scale は整数のみ。
    """
    if target_n_households <= 0 or target_n_households % SAMPLE_CASE_HOUSEHOLDS != 0:
        msg = (
            f"n_households must be a positive multiple of {SAMPLE_CASE_HOUSEHOLDS}, "
            f"got {target_n_households}"
        )
        raise ValueError(msg)

    scale = target_n_households // SAMPLE_CASE_HOUSEHOLDS
    target_dir.mkdir(parents=True, exist_ok=True)
    for name in COUNT_CSVS:
        df = pd.read_csv(SAMPLE_CASE_DIR / name)
        df["count"] = df["count"] * scale
        df.to_csv(target_dir / name, index=False)
    for name in COPY_CSVS:
        shutil.copy(SAMPLE_CASE_DIR / name, target_dir / name)


def _load_init_stats(input_dir: Path) -> InitStats:
    """入力 CSV ディレクトリから InitStats を組み立てる."""
    return InitStats(
        family_type_counts=load_family_type_counts(input_dir / "family_type_counts.csv"),
        children_count_dist=load_children_count_dist(input_dir / "children_count_dist.csv"),
        demographic_by_age_sex=load_demographic_by_age_sex(
            input_dir / "demographic_by_age_sex.csv"
        ),
        family_type_mapping=load_family_type_mapping(CONFIGS_DIR / "family_type_mapping.yaml"),
        household_size_by_family_type=load_household_size_by_family_type(
            input_dir / "household_size_by_family_type.csv"
        ),
        demographic_by_family_type_role=load_demographic_by_family_type_role(
            input_dir / "demographic_by_family_type_role.csv"
        ),
    )


def _build_transition(
    *,
    transition_kind: str,
    arrays: object,
    demo_by_age_sex: object,
    demo_ft_role: object,
    seed_registry: SeedRegistry,
) -> AgeChangeTransition | AgeSwapTransition | HybridTransition:
    """transition_kind から AgeChange / AgeSwap / Hybrid を構築する."""
    # arrays / demo の型は呼び出し側で揃っているため受け流す
    arrays_typed = arrays  # type: ignore[assignment]
    demo_typed = demo_by_age_sex  # type: ignore[assignment]
    demo_ft_typed = demo_ft_role  # type: ignore[assignment]

    if transition_kind == "age_change":
        return AgeChangeTransition(
            arrays=arrays_typed,  # type: ignore[arg-type]
            demo_by_age_sex=demo_typed,  # type: ignore[arg-type]
            rng=seed_registry.rng("transition_change"),
            demo_ft_role=demo_ft_typed,  # type: ignore[arg-type]
        )
    if transition_kind == "age_swap":
        return AgeSwapTransition(
            arrays=arrays_typed,  # type: ignore[arg-type]
            demo_by_age_sex=demo_typed,  # type: ignore[arg-type]
            rng=seed_registry.rng("transition_swap"),
            demo_ft_role=demo_ft_typed,  # type: ignore[arg-type]
        )
    if transition_kind == "hybrid":
        from synthpop_jp.optimize.transitions import LinearPChange

        change = AgeChangeTransition(
            arrays=arrays_typed,  # type: ignore[arg-type]
            demo_by_age_sex=demo_typed,  # type: ignore[arg-type]
            rng=seed_registry.rng("transition_change"),
            demo_ft_role=demo_ft_typed,  # type: ignore[arg-type]
        )
        swap = AgeSwapTransition(
            arrays=arrays_typed,  # type: ignore[arg-type]
            demo_by_age_sex=demo_typed,  # type: ignore[arg-type]
            rng=seed_registry.rng("transition_swap"),
            demo_ft_role=demo_ft_typed,  # type: ignore[arg-type]
        )
        return HybridTransition(
            change=change,
            swap=swap,
            p_change=LinearPChange(start=HYBRID_P_CHANGE_START, end=HYBRID_P_CHANGE_END),
            rng=seed_registry.rng("transition_hybrid"),
        )
    msg = (
        f"Unknown transition_kind {transition_kind!r}; "
        "expected one of {'age_change', 'age_swap', 'hybrid'}"
    )
    raise ValueError(msg)


def _stat_l1_summary(objective: ObjectiveState) -> dict[str, float]:
    """ObjectiveState の各 stat の L1 を ``"stat_{i}"`` 形式で返す."""
    return {f"stat_{i:02d}": float(s.l1_score()) for i, s in enumerate(objective.stats)}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_one(
    *,
    seed: int,
    transition_kind: str,
    evals_per_agent: int,
    n_households: int,
    t0: float = DEFAULT_T0,
    alpha: float = DEFAULT_ALPHA,
) -> RunResult:
    """1 つの seed × transition × evals_per_agent で SA を 1 回回す.

    spec §11.4.1（原論文準拠モード, Murata 式(3) の 21 統計, weight=1）で
    SA を回し、best_score と 21 統計別 L1 を返す。

    Parameters
    ----------
    seed : int
        ``SeedRegistry(root=seed)`` に渡す根 seed。
    transition_kind : str
        ``"age_change"`` / ``"age_swap"`` / ``"hybrid"``。
    evals_per_agent : int
        SA の停止条件。``max_iters = evals_per_agent * n_persons`` 相当として
        ``AnnealingConfig.evals_per_agent`` に渡す。
    n_households : int
        入力世帯数（100 の倍数）。data/sample_case/ を整数倍スケールする。
    t0 : float
        冷却スケジュールの初期温度。
    alpha : float
        指数冷却の冷却率（``T(i+1) = alpha * T(i)``）。

    Returns
    -------
    RunResult
        best_score, stat_l1, 経過時間。
    """
    with TemporaryDirectory() as tmp_root:
        tmp_dir = Path(tmp_root) / "input"
        _scale_sample_case(n_households, tmp_dir)

        stats = _load_init_stats(tmp_dir)
        age_diff_pc = load_age_diff_parent_child(tmp_dir / "age_diff_parent_child.csv")
        age_diff_couple = load_age_diff_couple(tmp_dir / "age_diff_couple.csv")
        demo_ft_role = stats.demographic_by_family_type_role or []

        seeds = SeedRegistry(root=seed)

        # 初期人口生成（zero_error_init で F-W 統計 L1=0 から始める）
        arrays = generate_initial_population(
            stats,
            seeds.rng("init"),
            use_zero_error_init=True,
        )

        # strict_extended（A,B,C + 9 ft × 2 sex pyramid = 21 統計）
        objective = ObjectiveState.from_arrays(
            arrays=arrays,
            age_diff_parent_child=age_diff_pc,
            age_diff_couple=age_diff_couple,
            demographic_by_age_sex=stats.demographic_by_age_sex,
            demo_ft_role=demo_ft_role,
            use_family_type_pyramid=True,
            exclude_male_female_pyramid=True,
        )

        transition = _build_transition(
            transition_kind=transition_kind,
            arrays=arrays,
            demo_by_age_sex=stats.demographic_by_age_sex,
            demo_ft_role=demo_ft_role,
            seed_registry=seeds,
        )

        cooling = ExponentialCooling(T0=t0, alpha=alpha)
        n_persons = arrays.n_persons
        max_iters = evals_per_agent * max(n_persons, 1)
        config = AnnealingConfig(
            max_iters=max_iters,
            T0=t0,
            alpha=alpha,
            trace_enabled=False,
            evals_per_agent=evals_per_agent,
            checkpoint_every_n_iters=0,
        )
        runner = SARunner(rng=seeds.rng("sa_runner"))

        t_start = time.perf_counter()
        result = runner.run(
            arrays=arrays,
            objective=objective,
            transition=transition,
            cooling=cooling,
            config=config,
            trace_path=None,
            progress_enabled=False,
        )
        elapsed = time.perf_counter() - t_start

        best_score = float(result.final_state.best_score)

        # best_arrays から目的関数を再構築して 21 統計の L1 を集計
        best_obj = ObjectiveState.from_arrays(
            arrays=result.best_arrays,
            age_diff_parent_child=age_diff_pc,
            age_diff_couple=age_diff_couple,
            demographic_by_age_sex=stats.demographic_by_age_sex,
            demo_ft_role=demo_ft_role,
            use_family_type_pyramid=True,
            exclude_male_female_pyramid=True,
        )
        stat_l1 = _stat_l1_summary(best_obj)

    return RunResult(
        seed=seed,
        transition_kind=transition_kind,
        n_households=n_households,
        evals_per_agent=evals_per_agent,
        best_score=best_score,
        stat_l1=stat_l1,
        elapsed_seconds=elapsed,
    )
