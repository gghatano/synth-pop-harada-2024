"""Multi-trial improvement loop runner (Issue #119, Step 5).

``run_improve_loop`` は base_settings に対して n_trials 回の SA を回し、
各 trial の合成人口と評価指標を ``output_root/<run_id>/trial_NNN/`` に書き出す。

実行モデル:

1. 戦略インスタンス（``ImproveStrategy``）を ``strategy_name`` から組む
2. 各 trial で ``strategy.next_config(history)`` を呼んで Settings を得る
3. その Settings で SA を回し（CLI ``generate`` と等価）、合成 CSV を書き出す
4. 評価メトリクスを集約（CLI ``evaluate --no-report`` 相当の最小集合）
5. ``TrialResult`` を history に append し、次の trial へ
6. 全 trial 終了後、composite objective での best を選び、``best_config.yaml`` /
   ``summary.md`` / （pareto 戦略時のみ）``pareto_front.md`` を出力する

決定性
------
同一 ``base_settings`` × 同一 ``strategy_name`` × 同一 ``seed`` で 2 回呼ぶと
``best_config.yaml`` が bitwise 一致する（spec §19.3）。SA 内部の RNG は
``Settings.seed`` を ``trial_id`` でずらしたもの（``settings.seed + trial_id``）
を起点に ``SeedRegistry`` に渡す。
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import yaml

from synthpop_jp.config import Settings

if TYPE_CHECKING:
    from synthpop_jp.improve.strategy import ImproveStrategy


StrategyName = Literal["rule_based", "pareto", "random_search"]
ObjectiveName = Literal["composite", "statistical_fit", "utility", "privacy"]


@dataclass(frozen=True)
class TrialResult:
    """1 trial の結果.

    Attributes
    ----------
    trial_id : int
        1-origin の trial 番号。
    config : Settings
        この trial で使った Settings。
    metrics : dict[str, float]
        評価指標。最低限 ``best_score`` を含む。3 目的の代理指標として
        ``statistical_fit`` / ``utility`` / ``privacy`` の正規化済み値も入れる。
    elapsed_s : float
        この trial の壁時計時間（秒）。
    output_dir : Path | None
        この trial の成果物を書き出したディレクトリ。dry_run 時は ``None``。
    """

    trial_id: int
    config: Settings
    metrics: dict[str, float] = field(default_factory=lambda: dict[str, float]())
    elapsed_s: float = 0.0
    output_dir: Path | None = None


@dataclass(frozen=True)
class ImproveLoopResult:
    """改善ループ全体の結果.

    Attributes
    ----------
    run_id : str
        この run の ID（出力ディレクトリ名に使う）。
    history : list[TrialResult]
        各 trial の結果。
    best : TrialResult
        composite objective での best trial。
    output_dir : Path
        ``outputs/improve/<run_id>/`` のパス。
    """

    run_id: str
    history: list[TrialResult]
    best: TrialResult
    output_dir: Path


def build_strategy(
    name: StrategyName,
    base_settings: Settings,
    *,
    seed: int = 42,
) -> ImproveStrategy:
    """戦略名から ImproveStrategy インスタンスを組み立てる."""
    from synthpop_jp.improve.strategy import (
        ParetoStrategy,
        RandomSearchStrategy,
        RuleBasedStrategy,
    )

    if name == "rule_based":
        return RuleBasedStrategy(base_settings, seed=seed)
    if name == "pareto":
        return ParetoStrategy(base_settings, seed=seed)
    if name == "random_search":
        return RandomSearchStrategy(base_settings, seed=seed)
    msg = f"Unknown strategy name: {name!r} (expected rule_based / pareto / random_search)"
    raise ValueError(msg)


def _format_run_id(seed: int, strategy_name: str) -> str:
    """run_id を決定論的に作る（時刻に依存させない）."""
    return f"{strategy_name}_seed{seed}"


def _run_one_trial(
    settings: Settings,
    trial_dir: Path,
) -> dict[str, float]:
    """1 trial 分の SA + 評価を実行し、メトリクス dict を返す.

    内部では ``synthpop-jp generate`` 相当の処理を直接呼ぶ。subprocess を
    起動しないので CI で速い。出力 CSV と metrics.json は ``trial_dir`` に
    書き出す。

    Returns
    -------
    dict[str, float]
        ``best_score`` / ``initial_score`` / ``aggregate.l1.*`` /
        ``rare_cell.unique_rate`` / 3 目的代理値（statistical_fit / utility /
        privacy）を含む。
    """
    import csv

    from synthpop_jp.evaluate.aggregate_metrics import AggregateStatL1Evaluator
    from synthpop_jp.evaluate.rare_cell_metrics import RareCellEvaluator
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
        ConstantPChange,
        HybridTransition,
        LinearPChange,
    )
    from synthpop_jp.rng import SeedRegistry

    # --- 入力 CSV 読み込み ---
    input_dir = settings.input_dir
    mapping_candidates = [
        settings.family_type_mapping,
        input_dir.parent / "family_type_mapping.yaml",
        Path(__file__).resolve().parents[3] / "configs" / "family_type_mapping.yaml",
    ]
    mapping_path: Path | None = None
    for c in mapping_candidates:
        if c is not None and Path(c).exists():
            mapping_path = Path(c)
            break
    if mapping_path is None:
        msg = (
            "family_type_mapping.yaml が見つかりません"
            "（settings.family_type_mapping か configs/ に置いてください）"
        )
        raise FileNotFoundError(msg)

    family_type_counts = load_family_type_counts(input_dir / "family_type_counts.csv")
    children_count_dist = load_children_count_dist(
        input_dir / "children_count_dist.csv",
        mapping_path=mapping_path,
    )
    demographic_by_age_sex = load_demographic_by_age_sex(input_dir / "demographic_by_age_sex.csv")
    family_type_mapping = load_family_type_mapping(mapping_path)

    household_size_by_family_type = None
    hh_size_path = input_dir / "household_size_by_family_type.csv"
    if hh_size_path.exists():
        household_size_by_family_type = load_household_size_by_family_type(hh_size_path)

    demographic_by_family_type_role = None
    demo_ft_role_path = input_dir / "demographic_by_family_type_role.csv"
    if demo_ft_role_path.exists():
        demographic_by_family_type_role = load_demographic_by_family_type_role(demo_ft_role_path)

    age_diff_couple = load_age_diff_couple(input_dir / "age_diff_couple.csv")
    age_diff_parent_child = load_age_diff_parent_child(input_dir / "age_diff_parent_child.csv")

    # --- 初期人口生成 ---
    seed_reg = SeedRegistry(root=settings.seed)
    init_stats = InitStats(
        family_type_counts=family_type_counts,
        children_count_dist=children_count_dist,
        demographic_by_age_sex=demographic_by_age_sex,
        family_type_mapping=family_type_mapping,
        household_size_by_family_type=household_size_by_family_type,
        demographic_by_family_type_role=demographic_by_family_type_role,
    )
    arrays = generate_initial_population(
        init_stats,
        seed_reg.rng("init"),
        use_zero_error_init=settings.objective.use_zero_error_init,
    )

    # --- ObjectiveState ---
    objective = ObjectiveState.from_arrays(
        arrays=arrays,
        age_diff_parent_child=age_diff_parent_child,
        age_diff_couple=age_diff_couple,
        demographic_by_age_sex=demographic_by_age_sex,
        demo_ft_role=demographic_by_family_type_role,
        use_family_type_pyramid=settings.objective.use_family_type_pyramid,
        exclude_male_female_pyramid=settings.objective.exclude_male_female_pyramid,
    )
    initial_score = float(objective.total_score)

    # --- transition / cooling / SA ---
    ann = settings.annealing
    transition: AgeChangeTransition | AgeSwapTransition | HybridTransition
    if ann.transition_kind == "age-swap":
        transition = AgeSwapTransition(
            arrays=arrays,
            demo_by_age_sex=demographic_by_age_sex,
            rng=seed_reg.rng("sa_transition"),
            demo_ft_role=demographic_by_family_type_role,
        )
    elif ann.transition_kind == "hybrid":
        change = AgeChangeTransition(
            arrays=arrays,
            demo_by_age_sex=demographic_by_age_sex,
            rng=seed_reg.rng("sa_change"),
            demo_ft_role=demographic_by_family_type_role,
        )
        swap = AgeSwapTransition(
            arrays=arrays,
            demo_by_age_sex=demographic_by_age_sex,
            rng=seed_reg.rng("sa_swap"),
            demo_ft_role=demographic_by_family_type_role,
        )
        schedule: ConstantPChange | LinearPChange
        if ann.p_change_schedule == "linear":
            assert ann.p_change_end is not None
            schedule = LinearPChange(start=ann.p_change, end=ann.p_change_end)
        else:
            schedule = ConstantPChange(ann.p_change)
        transition = HybridTransition(
            change=change,
            swap=swap,
            p_change=schedule,
            rng=seed_reg.rng("sa_hybrid_chooser"),
        )
    else:
        transition = AgeChangeTransition(
            arrays=arrays,
            demo_by_age_sex=demographic_by_age_sex,
            rng=seed_reg.rng("sa_transition"),
            demo_ft_role=demographic_by_family_type_role,
        )

    cooling = ExponentialCooling(T0=ann.T0, alpha=ann.alpha)
    sa_runner = SARunner(rng=seed_reg.rng("sa_runner"))
    sa_result = sa_runner.run(
        arrays=arrays,
        objective=objective,
        transition=transition,
        cooling=cooling,
        config=ann,
        trace_path=None,
        progress_enabled=False,
        resume_from=None,
    )

    best_arrays = sa_result.best_arrays
    best_score = float(sa_result.final_state.best_score)
    best_households = best_arrays.to_households()

    # --- 出力ディレクトリと CSV 書き出し ---
    trial_dir.mkdir(parents=True, exist_ok=True)
    hh_csv = trial_dir / "synthetic_households.csv"
    with hh_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["household_id", "family_type", "household_size"])
        writer.writeheader()
        for hh in best_households:
            writer.writerow(
                {
                    "household_id": f"HH_{hh.household_id:06d}",
                    "family_type": hh.family_type,
                    "household_size": len(hh.members),
                },
            )

    persons_csv = trial_dir / "synthetic_persons.csv"
    person_id = 1
    with persons_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["person_id", "household_id", "family_type", "role", "sex", "age"],
        )
        writer.writeheader()
        for hh in best_households:
            for person in hh.members:
                writer.writerow(
                    {
                        "person_id": f"P_{person_id:06d}",
                        "household_id": f"HH_{hh.household_id:06d}",
                        "family_type": hh.family_type,
                        "role": person.role,
                        "sex": person.sex,
                        "age": person.age,
                    },
                )
                person_id += 1

    # --- 評価（aggregate L1 + rare cell）---
    agg_eval = AggregateStatL1Evaluator(
        age_diff_parent_child=age_diff_parent_child,
        age_diff_couple=age_diff_couple,
        demographic_by_age_sex=demographic_by_age_sex,
        demo_ft_role=demographic_by_family_type_role,
        use_family_type_pyramid=settings.objective.use_family_type_pyramid,
        exclude_male_female_pyramid=settings.objective.exclude_male_female_pyramid,
    )
    rare_eval = RareCellEvaluator()
    metrics: dict[str, float] = {
        "initial_score": initial_score,
        "best_score": best_score,
        "n_persons": float(best_arrays.n_persons),
    }
    metrics.update(agg_eval.evaluate(best_arrays))
    metrics.update(rare_eval.evaluate(best_arrays))

    # 3 目的代理値を計算（spec §14.4）。すべて「小さいほど良い」前提で正規化。
    # - statistical_fit: aggregate.l1.total（A+B+C+D+E の合計、または strict_extended）
    # - utility: best_score（SA 終了スコア=広義の utility 代理。narrow utility は重いので
    #   後続 issue で paper_results 側に置く）
    # - privacy: rare cell unique 率（高いほど一意化リスク高 → 値が小さいほど良い）
    statistical_fit = float(metrics.get("aggregate.l1.total", best_score))
    utility = float(best_score / max(initial_score, 1e-9))
    privacy = float(metrics.get("rare_cell.unique_rate", 0.0))
    metrics["statistical_fit"] = statistical_fit
    metrics["utility"] = utility
    metrics["privacy"] = privacy

    # --- metrics.json を書き出す ---
    (trial_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return metrics


def _settings_to_yaml_dict(settings: Settings) -> dict[str, object]:
    """Convert Settings into a YAML-serialisable dict (Path → str).

    決定性のため、絶対パス（``input_dir`` / ``output_dir`` / ``family_type_mapping``）
    は **basename のみ** に正規化する。これにより、同一 seed × 同一戦略で
    異なる tmp_path から呼ばれても ``best_config.yaml`` が bitwise 一致する。
    元の絶対パスは ``summary.md`` に書く。
    """
    raw = settings.model_dump(mode="json")
    for key in ("input_dir", "output_dir", "family_type_mapping"):
        v = raw.get(key)
        if isinstance(v, str):
            raw[key] = Path(v).name  # basename だけ残す
    return raw


def _write_summary_md(
    *,
    output_dir: Path,
    history: list[TrialResult],
    best: TrialResult,
    strategy_name: str,
    seed: int,
) -> None:
    """summary.md を書き出す（非技術者でも読めるように 30 秒で要点把握）."""
    lines: list[str] = []
    lines.append(f"# 改善ループ結果サマリ ({strategy_name}, seed={seed})\n")
    lines.append(
        f"全 {len(history)} trial の SA を実行し、composite objective (best_score) で "
        f"最も良かった trial は **trial_{best.trial_id:03d}** でした。\n",
    )
    lines.append("## ベストの根拠\n")
    lines.append(f"- best_score: {best.metrics.get('best_score', float('nan')):.3f}")
    lines.append(f"- statistical_fit: {best.metrics.get('statistical_fit', float('nan')):.3f}")
    lines.append(f"- utility: {best.metrics.get('utility', float('nan')):.3f}")
    lines.append(f"- privacy: {best.metrics.get('privacy', float('nan')):.3f}\n")
    lines.append("## 全 trial 一覧\n")
    lines.append("| trial | best_score | statistical_fit | utility | privacy | 経過(秒) |")
    lines.append("|-------|-----------:|----------------:|--------:|--------:|---------:|")
    for tr in history:
        m = tr.metrics
        lines.append(
            f"| {tr.trial_id:03d} | "
            f"{m.get('best_score', float('nan')):.3f} | "
            f"{m.get('statistical_fit', float('nan')):.3f} | "
            f"{m.get('utility', float('nan')):.3f} | "
            f"{m.get('privacy', float('nan')):.3f} | "
            f"{tr.elapsed_s:.2f} |",
        )
    lines.append("")
    lines.append("## 4 種の objective 別ベスト\n")
    from synthpop_jp.improve.selector import select_best

    for obj in ("composite", "statistical_fit", "utility", "privacy"):
        try:
            top = select_best(history, obj)  # type: ignore[arg-type]
            lines.append(f"- {obj}: trial_{top.trial_id:03d}")
        except ValueError:
            lines.append(f"- {obj}: 該当なし")
    lines.append("")

    (output_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def _write_pareto_md(
    *,
    output_dir: Path,
    history: list[TrialResult],
) -> None:
    """pareto_front.md を書き出す。non-dominated trial を表形式で並べる."""
    from synthpop_jp.improve.pareto import extract_non_dominated
    from synthpop_jp.improve.strategy import PARETO_OBJECTIVE_KEYS

    if not history:
        (output_dir / "pareto_front.md").write_text("# Pareto front\n\n(空)\n", encoding="utf-8")
        return

    points = [
        tuple(float(tr.metrics.get(k, float("inf"))) for k in PARETO_OBJECTIVE_KEYS)
        for tr in history
    ]
    nd = extract_non_dominated(points)

    lines: list[str] = []
    lines.append("# Pareto front\n")
    lines.append(
        "3 目的（statistical_fit / utility / privacy）の non-dominated set。"
        "各値はすべて「小さいほど良い」前提です。\n",
    )
    lines.append("| trial | statistical_fit | utility | privacy |")
    lines.append("|-------|----------------:|--------:|--------:|")
    for i in nd:
        tr = history[i]
        m = tr.metrics
        lines.append(
            f"| {tr.trial_id:03d} | "
            f"{m.get('statistical_fit', float('nan')):.3f} | "
            f"{m.get('utility', float('nan')):.3f} | "
            f"{m.get('privacy', float('nan')):.3f} |",
        )
    lines.append("")

    (output_dir / "pareto_front.md").write_text("\n".join(lines), encoding="utf-8")


def run_improve_loop(
    base_settings: Settings,
    strategy_name: StrategyName,
    n_trials: int,
    *,
    seed: int = 42,
    output_root: Path | None = None,
) -> ImproveLoopResult:
    """multi-trial 改善ループを実行する.

    Parameters
    ----------
    base_settings : Settings
        ベース Settings。各 trial で改善対象 4 軸が上書きされる。
    strategy_name : StrategyName
        ``"rule_based"`` / ``"pareto"`` / ``"random_search"`` のいずれか。
    n_trials : int
        実行する trial 数（1 以上）。
    seed : int
        改善戦略内部の乱数 seed（ジッタ・ランダムサンプリングに使う）。
        各 trial の SA seed は ``base_settings.seed + trial_id`` を使う
        （SA 内部の独立 seed を確保しつつ、再現性を保つ）。
    output_root : Path | None
        出力ルート。省略時は ``base_settings.output_dir / "improve"``。
        実際の出力は ``output_root / <run_id>/`` 以下。

    Returns
    -------
    ImproveLoopResult
        全 trial の結果と best、出力ディレクトリ。
    """
    if n_trials < 1:
        msg = f"n_trials は 1 以上が必要 (got {n_trials})"
        raise ValueError(msg)

    if output_root is None:
        output_root = base_settings.output_dir / "improve"

    run_id = _format_run_id(seed=seed, strategy_name=strategy_name)
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    strategy = build_strategy(strategy_name, base_settings, seed=seed)

    history: list[TrialResult] = []
    for i in range(n_trials):
        trial_id = i + 1
        trial_dir = run_dir / f"trial_{trial_id:03d}"

        # 戦略から次の Settings を取得（履歴は決定論的）
        next_settings = strategy.next_config(history)
        # SA 用の seed を trial_id でずらす（同一 base seed × 全 trial 一致を避ける）
        trial_settings = next_settings.model_copy(
            update={
                "seed": int(base_settings.seed) + trial_id,
                "output_dir": trial_dir,
            },
        )

        t_start = time.perf_counter()
        metrics = _run_one_trial(trial_settings, trial_dir)
        elapsed = time.perf_counter() - t_start

        history.append(
            TrialResult(
                trial_id=trial_id,
                config=trial_settings,
                metrics=metrics,
                elapsed_s=elapsed,
                output_dir=trial_dir,
            ),
        )

    # best 選択
    from synthpop_jp.improve.selector import select_best

    best = select_best(history, "composite")

    # best_config.yaml
    best_yaml = run_dir / "best_config.yaml"
    best_yaml.write_text(
        yaml.safe_dump(
            _settings_to_yaml_dict(best.config),
            default_flow_style=False,
            sort_keys=True,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    # summary.md
    _write_summary_md(
        output_dir=run_dir,
        history=history,
        best=best,
        strategy_name=strategy_name,
        seed=seed,
    )

    # pareto_front.md (pareto 戦略時のみ)
    if strategy_name == "pareto":
        _write_pareto_md(output_dir=run_dir, history=history)

    return ImproveLoopResult(
        run_id=run_id,
        history=history,
        best=best,
        output_dir=run_dir,
    )


__all__ = [
    "ImproveLoopResult",
    "ObjectiveName",
    "StrategyName",
    "TrialResult",
    "build_strategy",
    "run_improve_loop",
]
