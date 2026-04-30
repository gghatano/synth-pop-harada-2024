"""9 family_types の SA 収束記録（Issue #95）.

sample_case を入力に、``use_zero_error_init=True`` + extended objective +
HybridTransition で SA を seed×5 回し、family_type ごとの F-W (family_type ×
sex pyramid) L1 推移を記録する。

実行例::

    uv run python experiments/2026-04-30-9-family-types-coverage/run.py

成功条件（Issue #95）:
- 9 family_types すべてで初期 F-W L1 が default <= 0 まで下がる（zero_error 効果）
- SA 後に各 family_type の F-W L1 が初期 L1 以下（単調か非劣化）
"""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path

import numpy as np

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
from synthpop_jp.optimize.objective import ObjectiveState, family_type_pyramid_index
from synthpop_jp.optimize.transitions import AgeChangeTransition
from synthpop_jp.rng import SeedRegistry

EXPERIMENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = EXPERIMENT_DIR.parents[1]
DATA_DIR = REPO_ROOT / "data" / "sample_case"
CONFIGS_DIR = REPO_ROOT / "configs"
OUTPUTS_DIR = EXPERIMENT_DIR / "outputs"

NINE_FAMILY_TYPES: tuple[str, ...] = (
    "single",
    "couple",
    "couple_and_children",
    "father_and_children",
    "mother_and_children",
    "couple_and_parents",
    "couple_and_a_parent",
    "couple_children_and_parents",
    "couple_children_and_a_parent",
)

SEEDS: tuple[int, ...] = (42, 43, 44, 45, 46)
MAX_ITERS: int = 20_000
T0: float = 1.0
ALPHA: float = 0.999


def _load_stats() -> InitStats:
    return InitStats(
        family_type_counts=load_family_type_counts(DATA_DIR / "family_type_counts.csv"),
        children_count_dist=load_children_count_dist(DATA_DIR / "children_count_dist.csv"),
        demographic_by_age_sex=load_demographic_by_age_sex(DATA_DIR / "demographic_by_age_sex.csv"),
        family_type_mapping=load_family_type_mapping(CONFIGS_DIR / "family_type_mapping.yaml"),
        household_size_by_family_type=load_household_size_by_family_type(
            DATA_DIR / "household_size_by_family_type.csv"
        ),
        demographic_by_family_type_role=load_demographic_by_family_type_role(
            DATA_DIR / "demographic_by_family_type_role.csv"
        ),
    )


def _l1_per_family_type(obj: ObjectiveState) -> dict[str, float]:
    """``stats`` から family_type ごとの F-W (M+F) L1 を集計."""
    offset = obj.family_type_pyramid_offset
    if offset is None:
        msg = "family_type_pyramid_offset is None — extended objective が無効"
        raise RuntimeError(msg)
    n_sex = 2
    out: dict[str, float] = {}
    for ft_name in NINE_FAMILY_TYPES:
        ft_id = obj.arrays.family_reg.id_of(ft_name)
        l1 = 0.0
        for sex_id in range(n_sex):
            idx = family_type_pyramid_index(offset, ft_id, sex_id, n_sex=n_sex)
            l1 += obj.stats[idx].l1_score()
        out[ft_name] = l1
    return out


def run_one_seed(stats: InitStats, seed: int) -> dict[str, object]:
    """1 つの seed で初期生成 + SA を回し、L1 推移を返す."""
    age_diff_pc = load_age_diff_parent_child(DATA_DIR / "age_diff_parent_child.csv")
    age_diff_couple = load_age_diff_couple(DATA_DIR / "age_diff_couple.csv")

    # 1) zero_error_init で初期人口生成
    init_rng = SeedRegistry(root=seed).rng("init")
    arrays = generate_initial_population(stats, init_rng, use_zero_error_init=True)

    demo_ft_role = stats.demographic_by_family_type_role or []

    # 2) extended objective を構築
    objective = ObjectiveState.from_arrays(
        arrays=arrays,
        age_diff_parent_child=age_diff_pc,
        age_diff_couple=age_diff_couple,
        demographic_by_age_sex=stats.demographic_by_age_sex,
        demo_ft_role=demo_ft_role,
        use_family_type_pyramid=True,
    )
    initial_l1 = _l1_per_family_type(objective)
    initial_total = objective.total_score

    # 3) SA を回す（AgeChangeTransition で十分: 9 family_types coverage の確認が目的）
    sa_rng_root = SeedRegistry(root=seed)
    transition = AgeChangeTransition(
        arrays=arrays,
        demo_by_age_sex=stats.demographic_by_age_sex,
        rng=sa_rng_root.rng("transition"),
        demo_ft_role=demo_ft_role,
    )
    cooling = ExponentialCooling(T0=T0, alpha=ALPHA)
    config = AnnealingConfig(
        max_iters=MAX_ITERS,
        T0=T0,
        alpha=ALPHA,
        trace_enabled=False,
        evals_per_agent=0,
        checkpoint_every_n_iters=0,
    )
    runner = SARunner(rng=sa_rng_root.rng("sa_runner"))
    t0_clock = time.perf_counter()
    result = runner.run(
        arrays=arrays,
        objective=objective,
        transition=transition,
        cooling=cooling,
        config=config,
        trace_path=None,
        progress_enabled=False,
    )
    elapsed = time.perf_counter() - t0_clock

    # 4) 最良時点の L1 を取り直す（best_arrays から再構築）
    best_obj = ObjectiveState.from_arrays(
        arrays=result.best_arrays,
        age_diff_parent_child=age_diff_pc,
        age_diff_couple=age_diff_couple,
        demographic_by_age_sex=stats.demographic_by_age_sex,
        demo_ft_role=demo_ft_role,
        use_family_type_pyramid=True,
    )
    final_l1 = _l1_per_family_type(best_obj)

    return {
        "seed": seed,
        "initial_total": initial_total,
        "final_total": result.final_state.best_score,
        "initial_l1_per_ft": initial_l1,
        "final_l1_per_ft": final_l1,
        "elapsed_seconds": elapsed,
    }


def main() -> None:
    """seed×5 で SA を回し、family_type ごとの L1 を 3 つの CSV/JSON に書き出す."""
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    stats = _load_stats()

    rows: list[dict[str, object]] = []
    for seed in SEEDS:
        print(f"running seed={seed} ...", flush=True)
        r = run_one_seed(stats, seed)
        rows.append(r)
        print(
            f"  seed={seed}: total {r['initial_total']:.0f} -> {r['final_total']:.0f} "
            f"({r['elapsed_seconds']:.2f}s)",
            flush=True,
        )

    # 1) raw JSON
    (OUTPUTS_DIR / "results.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # 2) per-seed × per-family_type の CSV (long format)
    csv_path = OUTPUTS_DIR / "l1_per_family_type.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["seed", "family_type", "initial_l1", "final_l1", "delta"])
        for r in rows:
            seed = r["seed"]
            init_map = r["initial_l1_per_ft"]
            final_map = r["final_l1_per_ft"]
            assert isinstance(init_map, dict)
            assert isinstance(final_map, dict)
            for ft in NINE_FAMILY_TYPES:
                init_val = float(init_map[ft])
                final_val = float(final_map[ft])
                writer.writerow([seed, ft, init_val, final_val, final_val - init_val])

    # 3) 集約: family_type ごとの mean / std
    agg_path = OUTPUTS_DIR / "summary.csv"
    with agg_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["family_type", "mean_initial_l1", "mean_final_l1", "mean_delta"])
        for ft in NINE_FAMILY_TYPES:
            init_vals: list[float] = []
            final_vals: list[float] = []
            for r in rows:
                im = r["initial_l1_per_ft"]
                fm = r["final_l1_per_ft"]
                assert isinstance(im, dict)
                assert isinstance(fm, dict)
                init_vals.append(float(im[ft]))
                final_vals.append(float(fm[ft]))
            mi = float(np.mean(init_vals))
            mf = float(np.mean(final_vals))
            writer.writerow([ft, mi, mf, mf - mi])

    print(f"wrote {csv_path}")
    print(f"wrote {agg_path}")
    print(f"wrote {OUTPUTS_DIR / 'results.json'}")


if __name__ == "__main__":
    main()
