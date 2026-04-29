"""Command line interface for synthpop-jp.

Phase 1 で実装するサブコマンド:
- ``quickstart``: sample_case からの端末 1 発合成人口生成
- ``validate-config``: config.yaml の事前バリデーション

Phase 2 以降は ``generate`` / ``evaluate`` / ``improve`` / ``compare`` を実装する。
"""

from __future__ import annotations

import logging
from enum import StrEnum
from pathlib import Path
from typing import Annotated, NoReturn

import typer
from rich.console import Console

console = Console()
err_console = Console(stderr=True)

app: typer.Typer = typer.Typer(
    name="synthpop-jp",
    help="synthpop-jp: Murata 2017 synthetic population generator + Harada 2024 evaluation.",
    no_args_is_help=True,
    add_completion=False,
)


class LogLevel(StrEnum):
    """ログレベルの選択肢."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


def _not_yet(command: str, phase: str) -> NoReturn:
    """Print a phase notice and exit non-zero.

    Using :class:`typer.Exit` here (rather than ``raise NotImplementedError``)
    ensures coverage flags the subcommand body when Phase 1+ forgets to
    replace it.
    """
    typer.secho(
        f"[{phase}] `{command}` is not yet implemented.",
        fg=typer.colors.YELLOW,
        err=True,
    )
    raise typer.Exit(code=2)


@app.command()
def quickstart(
    config: Annotated[
        Path | None,
        typer.Option("--config", help="設定ファイルのパス。省略時は configs/base.yaml を使う。"),
    ] = None,
    seed: Annotated[
        int | None,
        typer.Option("--seed", help="乱数シード。指定すると config の seed を上書きする。"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", help="ファイル書き出しをスキップして読み込みと生成のみ実行する。"
        ),
    ] = False,
    log_level: Annotated[
        LogLevel,
        typer.Option("--log-level", help="ログレベル。"),
    ] = LogLevel.INFO,
) -> None:
    """sample_case からの端末 1 発合成人口生成.

    ``data/sample_case/`` に同梱のダミー入力 CSV を読み込み、
    ``outputs/quickstart/`` に ``synthetic_households.csv``,
    ``synthetic_persons.csv``, ``metrics.json`` を出力する。

    10 秒以内に完走することを目標とする。
    """
    import csv
    import json
    from collections import Counter

    from pydantic import ValidationError

    from synthpop_jp.config import Settings
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
    from synthpop_jp.rng import SeedRegistry

    logging.basicConfig(level=getattr(logging, log_level.value))

    # --- 設定ロード ---
    if config is None:
        # pyproject.toml が置かれているリポジトリルートを起点に探す
        config = _find_default_config()

    console.print(f"[bold]設定ファイル:[/bold] {config}")

    try:
        settings = Settings.from_yaml(config)
    except FileNotFoundError:
        err_console.print(f"[red]エラー:[/red] 設定ファイルが見つかりません: {config}")
        raise typer.Exit(code=1) from None
    except ValidationError as exc:
        err_console.print(f"[red]設定ファイルのバリデーションエラー:[/red]\n{exc}")
        raise typer.Exit(code=1) from None

    # seed の上書き
    if seed is not None:
        settings = settings.model_copy(update={"seed": seed})

    input_dir = settings.input_dir
    output_dir = settings.output_dir

    # 相対パスの解決基点: pyproject.toml がある「プロジェクトルート」を優先し、
    # 見つからない場合は config ファイルの親ディレクトリを使う。
    base_dir = _find_project_root(config)
    if not input_dir.is_absolute():
        input_dir = base_dir / input_dir
    if not output_dir.is_absolute():
        output_dir = base_dir / output_dir

    console.print(f"[bold]入力ディレクトリ:[/bold] {input_dir}")
    console.print(f"[bold]出力ディレクトリ:[/bold] {output_dir}")
    console.print(f"[bold]seed:[/bold] {settings.seed}")

    # --- family_type_mapping.yaml を探す ---
    # settings に明示指定があればそちらを優先する
    if settings.family_type_mapping is not None:
        mapping_path = settings.family_type_mapping
        if not mapping_path.is_absolute():
            mapping_path = config.parent / mapping_path
    else:
        mapping_path = _find_family_type_mapping(config)

    # --- CSV 読み込み ---
    console.print("[bold]入力 CSV を読み込み中...[/bold]")

    try:
        family_type_counts = load_family_type_counts(input_dir / "family_type_counts.csv")
        children_count_dist = load_children_count_dist(
            input_dir / "children_count_dist.csv",
            mapping_path=mapping_path,
        )
        demographic_by_age_sex = load_demographic_by_age_sex(
            input_dir / "demographic_by_age_sex.csv"
        )
        family_type_mapping = load_family_type_mapping(mapping_path)

        # 任意 CSV
        household_size_by_family_type = None
        hh_size_path = input_dir / "household_size_by_family_type.csv"
        if hh_size_path.exists():
            household_size_by_family_type = load_household_size_by_family_type(hh_size_path)

        demographic_by_family_type_role = None
        demo_ft_role_path = input_dir / "demographic_by_family_type_role.csv"
        if demo_ft_role_path.exists():
            demographic_by_family_type_role = load_demographic_by_family_type_role(
                demo_ft_role_path
            )

        # age_diff_couple / age_diff_parent_child は読み込むが InitStats では使わない
        # （Phase 2 の SA で使用）
        _age_diff_couple = load_age_diff_couple(input_dir / "age_diff_couple.csv")
        _age_diff_parent_child = load_age_diff_parent_child(input_dir / "age_diff_parent_child.csv")
        del _age_diff_couple, _age_diff_parent_child

    except FileNotFoundError as exc:
        err_console.print(f"[red]入力ファイルが見つかりません:[/red] {exc}")
        raise typer.Exit(code=1) from None

    console.print("[green]CSV 読み込み完了[/green]")

    # --- 初期人口生成 ---
    console.print("[bold]初期人口を生成中...[/bold]")

    stats = InitStats(
        family_type_counts=family_type_counts,
        children_count_dist=children_count_dist,
        demographic_by_age_sex=demographic_by_age_sex,
        family_type_mapping=family_type_mapping,
        household_size_by_family_type=household_size_by_family_type,
        demographic_by_family_type_role=demographic_by_family_type_role,
    )

    rng = SeedRegistry(root=settings.seed).rng("init")
    arrays = generate_initial_population(stats, rng)
    households = arrays.to_households()

    n_households = len(households)
    n_persons = sum(len(hh.members) for hh in households)

    console.print(f"[green]生成完了:[/green] {n_households} 世帯 / {n_persons} 人")

    # --- メトリクス集計 ---
    family_type_counter: Counter[str] = Counter()
    size_counter: Counter[int] = Counter()

    for hh in households:
        family_type_counter[hh.family_type] += 1
        size_counter[len(hh.members)] += 1

    metrics: dict[str, object] = {
        "total_households": n_households,
        "total_persons": n_persons,
        "family_type_counts": dict(family_type_counter),
        "household_size_distribution": {str(k): v for k, v in sorted(size_counter.items())},
    }

    # --- dry-run ならここで終了 ---
    if dry_run:
        console.print("[yellow]--dry-run モード: ファイルを書き出しません[/yellow]")
        return

    # --- 出力ディレクトリ作成 ---
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- synthetic_households.csv 書き出し ---
    hh_csv_path = output_dir / "synthetic_households.csv"
    with hh_csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["household_id", "family_type", "household_size"])
        writer.writeheader()
        for hh in households:
            writer.writerow(
                {
                    "household_id": f"HH_{hh.household_id:06d}",
                    "family_type": hh.family_type,
                    "household_size": len(hh.members),
                }
            )

    # --- synthetic_persons.csv 書き出し ---
    persons_csv_path = output_dir / "synthetic_persons.csv"
    person_id = 1
    with persons_csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["person_id", "household_id", "family_type", "role", "sex", "age"]
        )
        writer.writeheader()
        for hh in households:
            for person in hh.members:
                writer.writerow(
                    {
                        "person_id": f"P_{person_id:06d}",
                        "household_id": f"HH_{hh.household_id:06d}",
                        "family_type": hh.family_type,
                        "role": person.role,
                        "sex": person.sex,
                        "age": person.age,
                    }
                )
                person_id += 1

    # --- metrics.json 書き出し ---
    metrics_path = output_dir / "metrics.json"
    with metrics_path.open("w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    console.print(f"[green]出力完了:[/green] {output_dir}")
    console.print(f"  {hh_csv_path.name}")
    console.print(f"  {persons_csv_path.name}")
    console.print(f"  {metrics_path.name}")


@app.command()
def generate(
    config: Annotated[
        Path | None,
        typer.Option("--config", help="設定ファイルのパス。省略時は configs/base.yaml を使う。"),
    ] = None,
    seed: Annotated[
        int | None,
        typer.Option("--seed", help="乱数シード。指定すると config の seed を上書きする。"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", help="ファイル書き出しをスキップして読み込みと SA のみ実行する。"
        ),
    ] = False,
    log_level: Annotated[
        LogLevel,
        typer.Option("--log-level", help="ログレベル。"),
    ] = LogLevel.INFO,
    resume: Annotated[
        Path | None,
        typer.Option(
            "--resume",
            help="再開するチェックポイントファイルのパス（.pkl.gz）。"
            "指定すると、直近 checkpoint から SA を再開する。",
        ),
    ] = None,
) -> None:
    """SA（シミュレーテッドアニーリング）最適化付きの合成人口生成.

    ``quickstart`` の発展版。初期人口生成のあとに SA 最適化を実行し、
    より目標統計に近い合成人口を出力する。

    出力先: ``output_dir/synthetic_households.csv``,
    ``synthetic_persons.csv``, ``metrics.json``（best_score 等を含む）。
    """
    import csv
    import json
    from collections import Counter

    from pydantic import ValidationError

    from synthpop_jp.config import Settings
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

    logging.basicConfig(level=getattr(logging, log_level.value))

    # --- 設定ロード ---
    if config is None:
        config = _find_default_config()

    console.print(f"[bold]設定ファイル:[/bold] {config}")

    try:
        settings = Settings.from_yaml(config)
    except FileNotFoundError:
        err_console.print(f"[red]エラー:[/red] 設定ファイルが見つかりません: {config}")
        raise typer.Exit(code=1) from None
    except ValidationError as exc:
        err_console.print(f"[red]設定ファイルのバリデーションエラー:[/red]\n{exc}")
        raise typer.Exit(code=1) from None

    # seed の上書き
    if seed is not None:
        settings = settings.model_copy(update={"seed": seed})

    input_dir = settings.input_dir
    output_dir = settings.output_dir
    annealing_cfg = settings.annealing

    # 相対パスの解決
    base_dir = _find_project_root(config)
    if not input_dir.is_absolute():
        input_dir = base_dir / input_dir
    if not output_dir.is_absolute():
        output_dir = base_dir / output_dir

    console.print(f"[bold]入力ディレクトリ:[/bold] {input_dir}")
    console.print(f"[bold]出力ディレクトリ:[/bold] {output_dir}")
    console.print(f"[bold]seed:[/bold] {settings.seed}")

    # --- family_type_mapping.yaml を探す ---
    if settings.family_type_mapping is not None:
        mapping_path = settings.family_type_mapping
        if not mapping_path.is_absolute():
            mapping_path = config.parent / mapping_path
    else:
        mapping_path = _find_family_type_mapping(config)

    # --- CSV 読み込み ---
    console.print("[bold]入力 CSV を読み込み中...[/bold]")

    try:
        family_type_counts = load_family_type_counts(input_dir / "family_type_counts.csv")
        children_count_dist = load_children_count_dist(
            input_dir / "children_count_dist.csv",
            mapping_path=mapping_path,
        )
        demographic_by_age_sex = load_demographic_by_age_sex(
            input_dir / "demographic_by_age_sex.csv"
        )
        family_type_mapping = load_family_type_mapping(mapping_path)

        household_size_by_family_type = None
        hh_size_path = input_dir / "household_size_by_family_type.csv"
        if hh_size_path.exists():
            household_size_by_family_type = load_household_size_by_family_type(hh_size_path)

        demographic_by_family_type_role = None
        demo_ft_role_path = input_dir / "demographic_by_family_type_role.csv"
        if demo_ft_role_path.exists():
            demographic_by_family_type_role = load_demographic_by_family_type_role(
                demo_ft_role_path
            )

        age_diff_couple = load_age_diff_couple(input_dir / "age_diff_couple.csv")
        age_diff_parent_child = load_age_diff_parent_child(input_dir / "age_diff_parent_child.csv")

    except FileNotFoundError as exc:
        err_console.print(f"[red]入力ファイルが見つかりません:[/red] {exc}")
        raise typer.Exit(code=1) from None

    console.print("[green]CSV 読み込み完了[/green]")

    # --- 初期人口生成 ---
    console.print("[bold]初期人口を生成中...[/bold]")

    stats = InitStats(
        family_type_counts=family_type_counts,
        children_count_dist=children_count_dist,
        demographic_by_age_sex=demographic_by_age_sex,
        family_type_mapping=family_type_mapping,
        household_size_by_family_type=household_size_by_family_type,
        demographic_by_family_type_role=demographic_by_family_type_role,
    )

    seed_reg = SeedRegistry(root=settings.seed)
    arrays = generate_initial_population(stats, seed_reg.rng("init"))

    console.print(f"[green]初期人口生成完了:[/green] {arrays.n_persons} 人")

    # --- ObjectiveState 構築 ---
    console.print("[bold]目的スコアを初期化中...[/bold]")
    objective = ObjectiveState.from_arrays(
        arrays=arrays,
        age_diff_parent_child=age_diff_parent_child,
        age_diff_couple=age_diff_couple,
        demographic_by_age_sex=demographic_by_age_sex,
        demo_ft_role=demographic_by_family_type_role,
        use_family_type_pyramid=settings.objective.use_family_type_pyramid,
        exclude_male_female_pyramid=settings.objective.exclude_male_female_pyramid,
    )
    initial_score = objective.total_score
    console.print(f"[green]初期スコア:[/green] {initial_score:.1f}")

    # --- SA 最適化 ---
    console.print(
        f"[bold]SA 最適化を実行中...[/bold] "
        f"(T0={annealing_cfg.T0}, alpha={annealing_cfg.alpha}, "
        f"evals_per_agent={annealing_cfg.evals_per_agent})"
    )

    transition: AgeChangeTransition | AgeSwapTransition | HybridTransition
    if annealing_cfg.transition_kind == "age-swap":
        transition = AgeSwapTransition(
            arrays=arrays,
            demo_by_age_sex=demographic_by_age_sex,
            rng=seed_reg.rng("sa_transition"),
            demo_ft_role=demographic_by_family_type_role,
        )
    elif annealing_cfg.transition_kind == "hybrid":
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
        if annealing_cfg.p_change_schedule == "linear":
            # validator が p_change_end != None を保証している
            assert annealing_cfg.p_change_end is not None
            schedule = LinearPChange(
                start=annealing_cfg.p_change,
                end=annealing_cfg.p_change_end,
            )
        else:
            schedule = ConstantPChange(annealing_cfg.p_change)
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
    cooling = ExponentialCooling(T0=annealing_cfg.T0, alpha=annealing_cfg.alpha)
    runner_sa = SARunner(rng=seed_reg.rng("sa_runner"))

    # --resume の事前検証（ファイルが存在しない場合は exit 1）
    if resume is not None and not resume.exists():
        err_console.print(f"[red]エラー:[/red] checkpoint ファイルが見つかりません: {resume}")
        raise typer.Exit(code=1)

    # trace.jsonl の書き出し先は dry_run でない場合にのみ設定する
    # progress_enabled は dry_run=True または log_level=ERROR のとき抑制する
    trace_path_for_run = output_dir / "trace.jsonl" if not dry_run else None
    progress_enabled_for_run = not dry_run and log_level != LogLevel.ERROR

    if resume is not None:
        console.print(f"[bold]checkpoint から再開:[/bold] {resume}")

    sa_result = runner_sa.run(
        arrays=arrays,
        objective=objective,
        transition=transition,
        cooling=cooling,
        config=annealing_cfg,
        trace_path=trace_path_for_run,
        progress_enabled=progress_enabled_for_run,
        resume_from=resume,
    )

    best_score = sa_result.final_state.best_score
    n_accepted = sa_result.final_state.n_accepted
    n_total = sa_result.final_state.n_total
    accept_rate = n_accepted / n_total if n_total > 0 else 0.0

    console.print(
        f"[green]SA 完了:[/green] best_score={best_score:.1f} "
        f"(initial={initial_score:.1f}, "
        f"improvement={100 * (1 - best_score / initial_score):.1f}%)"
    )
    console.print(f"  反復: {n_total}, 受理率: {accept_rate:.3f}")

    # best_arrays から世帯リストを取得
    best_households = sa_result.best_arrays.to_households()
    n_households = len(best_households)
    n_persons = sum(len(hh.members) for hh in best_households)

    # --- メトリクス集計 ---
    family_type_counter: Counter[str] = Counter()
    size_counter: Counter[int] = Counter()
    for hh in best_households:
        family_type_counter[hh.family_type] += 1
        size_counter[len(hh.members)] += 1

    metrics: dict[str, object] = {
        "total_households": n_households,
        "total_persons": n_persons,
        "initial_score": initial_score,
        "best_score": best_score,
        "improvement_rate": float(1 - best_score / initial_score) if initial_score > 0 else 0.0,
        "n_accepted": n_accepted,
        "n_total": n_total,
        "accept_rate": accept_rate,
        "family_type_counts": dict(family_type_counter),
        "household_size_distribution": {str(k): v for k, v in sorted(size_counter.items())},
    }

    # --- dry-run ならここで終了 ---
    if dry_run:
        console.print("[yellow]--dry-run モード: ファイルを書き出しません[/yellow]")
        return

    # --- 出力ディレクトリ作成 ---
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- synthetic_households.csv 書き出し ---
    hh_csv_path = output_dir / "synthetic_households.csv"
    with hh_csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["household_id", "family_type", "household_size"])
        writer.writeheader()
        for hh in best_households:
            writer.writerow(
                {
                    "household_id": f"HH_{hh.household_id:06d}",
                    "family_type": hh.family_type,
                    "household_size": len(hh.members),
                }
            )

    # --- synthetic_persons.csv 書き出し ---
    persons_csv_path = output_dir / "synthetic_persons.csv"
    person_id = 1
    with persons_csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["person_id", "household_id", "family_type", "role", "sex", "age"]
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
                    }
                )
                person_id += 1

    # --- metrics.json 書き出し ---
    metrics_path = output_dir / "metrics.json"
    with metrics_path.open("w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    console.print(f"[green]出力完了:[/green] {output_dir}")
    console.print(f"  {hh_csv_path.name}")
    console.print(f"  {persons_csv_path.name}")
    console.print(f"  {metrics_path.name}")
    if annealing_cfg.trace_enabled:
        console.print("  trace.jsonl")


@app.command()
def evaluate(
    config: Annotated[
        Path | None,
        typer.Option("--config", help="設定ファイルのパス。省略時は configs/base.yaml を使う。"),
    ] = None,
    real_persons_csv: Annotated[
        Path | None,
        typer.Option(
            "--real-persons-csv",
            help="CAP/TCAP 計算に使う real 個票 CSV。省略時は CAP をスキップ。",
        ),
    ] = None,
    no_report: Annotated[
        bool,
        typer.Option(
            "--no-report",
            help="report.md (Harada 2024 Table 13 形式) の出力を抑止する (Issue #78)。",
        ),
    ] = False,
    log_level: Annotated[
        LogLevel,
        typer.Option("--log-level", help="ログレベル。"),
    ] = LogLevel.INFO,
) -> None:
    """合成人口の品質を評価し、metrics.json に結果を追記する.

    ``generate`` 出力ディレクトリ（``settings.output_dir``）の
    ``synthetic_persons.csv`` から人口を再構築し、以下の評価器を順番に実行する:

    - ``AggregateStatL1Evaluator`` (Issue #59): 統計別 L1 誤差
    - ``RareCellEvaluator`` (Issue #61): family_type×age cell の rare/unique 率
    - ``CAPEvaluator`` (Issue #65): Generalized CAP / TCAP（``--real-persons-csv`` 指定時のみ）

    結果は ``output_dir/metrics.json`` に ``aggregate.l1.*`` / ``rare_cell.*`` /
    ``cap.*`` キーとして追記される。
    """
    import json
    import logging

    from pydantic import ValidationError

    from synthpop_jp.config import Settings
    from synthpop_jp.evaluate.aggregate_metrics import AggregateStatL1Evaluator
    from synthpop_jp.evaluate.attribute_inference import CAPEvaluator
    from synthpop_jp.evaluate.rare_cell_metrics import RareCellEvaluator
    from synthpop_jp.io.loaders import (
        load_age_diff_couple,
        load_age_diff_parent_child,
        load_demographic_by_age_sex,
        load_demographic_by_family_type_role,
    )
    from synthpop_jp.io.schemas import DemographicByFamilyTypeRoleRow
    from synthpop_jp.io.synthesized import reconstruct_population_arrays_from_persons_csv

    logging.basicConfig(level=getattr(logging, log_level.value))

    if config is None:
        config = _find_default_config()

    console.print(f"[bold]設定ファイル:[/bold] {config}")

    try:
        settings = Settings.from_yaml(config)
    except FileNotFoundError:
        err_console.print(f"[red]エラー:[/red] 設定ファイルが見つかりません: {config}")
        raise typer.Exit(code=1) from None
    except ValidationError as e:
        err_console.print(f"[red]設定の検証に失敗:[/red] {e}")
        raise typer.Exit(code=1) from None

    persons_csv = settings.output_dir / "synthetic_persons.csv"
    if not persons_csv.exists():
        err_console.print(
            f"[red]エラー:[/red] synthetic_persons.csv が見つかりません: {persons_csv}"
        )
        err_console.print("先に `synthpop-jp generate` を実行してください。")
        raise typer.Exit(code=1)

    console.print(f"[bold]評価対象:[/bold] {persons_csv}")
    arrays = reconstruct_population_arrays_from_persons_csv(persons_csv)
    console.print(
        f"[green]人口再構築完了:[/green] {len(set(int(h) for h in arrays.household_id))} 世帯 / "
        f"{arrays.n_persons} 人"
    )

    age_diff_parent_child = load_age_diff_parent_child(
        settings.input_dir / "age_diff_parent_child.csv"
    )
    age_diff_couple = load_age_diff_couple(settings.input_dir / "age_diff_couple.csv")
    demographic_by_age_sex = load_demographic_by_age_sex(
        settings.input_dir / "demographic_by_age_sex.csv"
    )

    # family_type 別 demographic pyramid (Issue #71)。任意入力。
    demo_ft_role: list[DemographicByFamilyTypeRoleRow] | None = None
    demo_ft_role_path = settings.input_dir / "demographic_by_family_type_role.csv"
    if demo_ft_role_path.exists():
        demo_ft_role = load_demographic_by_family_type_role(demo_ft_role_path)

    aggregate_evaluator = AggregateStatL1Evaluator(
        age_diff_parent_child=age_diff_parent_child,
        age_diff_couple=age_diff_couple,
        demographic_by_age_sex=demographic_by_age_sex,
        demo_ft_role=demo_ft_role,
        use_family_type_pyramid=settings.objective.use_family_type_pyramid,
        exclude_male_female_pyramid=settings.objective.exclude_male_female_pyramid,
    )
    rare_cell_evaluator = RareCellEvaluator()
    metrics: dict[str, float] = {
        **aggregate_evaluator.evaluate(arrays),
        **rare_cell_evaluator.evaluate(arrays),
    }

    # entry_points プラグイン (Issue #79). 第三者が `synthpop_jp.evaluators`
    # group で登録した evaluator を自動検出して呼ぶ。
    from synthpop_jp.evaluate.plugin import load_evaluator_plugins

    for plugin in load_evaluator_plugins():
        metrics.update(plugin.evaluate(arrays))

    if real_persons_csv is not None:
        if not real_persons_csv.exists():
            err_console.print(
                f"[red]エラー:[/red] --real-persons-csv が見つかりません: {real_persons_csv}"
            )
            raise typer.Exit(code=1)
        console.print(f"[bold]CAP holdout:[/bold] {real_persons_csv}")
        holdout = reconstruct_population_arrays_from_persons_csv(real_persons_csv)
        cap_evaluator = CAPEvaluator()
        metrics.update(cap_evaluator.evaluate(arrays, holdout))
    else:
        console.print("[yellow]--real-persons-csv 未指定のため CAP/TCAP はスキップ[/yellow]")

    # metrics.json に追記（既存キーは保持）
    metrics_path = settings.output_dir / "metrics.json"
    if metrics_path.exists():
        existing: dict[str, object] = json.loads(metrics_path.read_text(encoding="utf-8"))
    else:
        existing = {}
    existing.update(metrics)
    metrics_path.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    console.print("[green]評価完了:[/green]")
    for k, v in metrics.items():
        console.print(f"  {k}: {v:.1f}")
    console.print(f"[bold]metrics.json 更新:[/bold] {metrics_path}")

    # Table 13 形式 Markdown レポート (Issue #78)
    if not no_report:
        from synthpop_jp.reports.markdown import render_metrics_table13

        # existing は object 値も含むので、float 化できるものだけ通す
        report_metrics: dict[str, float] = {}
        for k, v in existing.items():
            if isinstance(v, (int, float)):
                report_metrics[k] = float(v)
        report_md = render_metrics_table13(report_metrics)
        report_path = settings.output_dir / "report.md"
        report_path.write_text(report_md, encoding="utf-8")
        console.print(f"[bold]report.md 更新:[/bold] {report_path}")


@app.command()
def improve(config: str = "configs/base.yaml", trials: int = 10) -> None:
    """Run the improvement loop (Phase 5 onward).

    Parameters
    ----------
    config : str
        Path to a YAML configuration file.
    trials : int
        Number of trials to execute.
    """
    del config, trials
    _not_yet("improve", "Phase 5")


@app.command()
def compare(experiment: str) -> None:
    """Compare multiple runs of an experiment (Phase 3b onward).

    Parameters
    ----------
    experiment : str
        Path to an experiment configuration.
    """
    del experiment
    _not_yet("compare", "Phase 3b")


@app.command("validate-config")
def validate_config(
    config: Annotated[Path, typer.Argument(help="バリデーション対象の YAML 設定ファイルのパス。")],
) -> None:
    """設定ファイルの事前バリデーションを実行する.

    pydantic モデルで config.yaml を検証し、有効なら exit 0 + 成功メッセージ、
    不正なら exit 1 + エラー詳細を表示する。
    """
    from pydantic import ValidationError

    from synthpop_jp.config import Settings

    try:
        Settings.from_yaml(config)
    except FileNotFoundError:
        err_console.print(f"[red]エラー:[/red] 設定ファイルが見つかりません: {config}")
        raise typer.Exit(code=1) from None
    except ValidationError as exc:
        err_console.print(f"[red]ValidationError:[/red]\n{exc}")
        raise typer.Exit(code=1) from None

    console.print(f"[green]✓ Config is valid:[/green] {config}")


def _find_project_root(config_path: Path) -> Path:
    """プロジェクトルートを返す.

    ``pyproject.toml`` が置かれているディレクトリを「プロジェクトルート」とみなす。
    config ファイルの親から順にたどり、見つからなければカレントディレクトリも探す。
    最終的に見つからない場合は config ファイルの親ディレクトリを返す。

    Parameters
    ----------
    config_path : Path
        設定ファイルのパス。

    Returns
    -------
    Path
        プロジェクトルートのディレクトリ。
    """
    # config ファイルの親からたどる
    for parent in [config_path.parent, *config_path.parents]:
        if (parent / "pyproject.toml").exists():
            return parent

    # カレントディレクトリからたどる
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / "pyproject.toml").exists():
            return parent

    return config_path.parent


def _find_default_config() -> Path:
    """デフォルト設定ファイルを探して返す.

    呼び出し時のカレントディレクトリ、または pyproject.toml が見つかる
    ディレクトリの ``configs/base.yaml`` を返す。

    Returns
    -------
    Path
        デフォルト設定ファイルのパス（存在しない場合も Path を返す）。
    """
    # カレントディレクトリから探索
    cwd = Path.cwd()
    candidate = cwd / "configs" / "base.yaml"
    if candidate.exists():
        return candidate

    # pyproject.toml が見つかる親ディレクトリまで遡る
    for parent in cwd.parents:
        if (parent / "pyproject.toml").exists():
            candidate = parent / "configs" / "base.yaml"
            if candidate.exists():
                return candidate

    return cwd / "configs" / "base.yaml"


def _find_family_type_mapping(config_path: Path) -> Path:
    """family_type_mapping.yaml を探して返す.

    以下の順で ``family_type_mapping.yaml`` を探す:
    1. config ファイルと同じディレクトリ
    2. config ファイルの親をたどって pyproject.toml が見つかるディレクトリの configs/
    3. カレントディレクトリの configs/
    4. カレントディレクトリの親をたどって pyproject.toml が見つかるディレクトリの configs/

    Parameters
    ----------
    config_path : Path
        設定ファイルのパス。

    Returns
    -------
    Path
        family_type_mapping.yaml のパス。見つからない場合は config と同じ親ディレクトリ
        の candidate を返す（FileNotFoundError はローダ側で発生する）。
    """
    # 1. config の親ディレクトリと同じ場所
    configs_dir = config_path.parent
    candidate = configs_dir / "family_type_mapping.yaml"
    if candidate.exists():
        return candidate

    # 2. config ファイルの親をたどって pyproject.toml が見つかるディレクトリ
    for parent in config_path.parents:
        if (parent / "pyproject.toml").exists():
            candidate = parent / "configs" / "family_type_mapping.yaml"
            if candidate.exists():
                return candidate

    # 3. カレントディレクトリの configs/
    cwd = Path.cwd()
    candidate = cwd / "configs" / "family_type_mapping.yaml"
    if candidate.exists():
        return candidate

    # 4. カレントディレクトリの親をたどって pyproject.toml
    for parent in cwd.parents:
        if (parent / "pyproject.toml").exists():
            candidate = parent / "configs" / "family_type_mapping.yaml"
            if candidate.exists():
                return candidate

    return configs_dir / "family_type_mapping.yaml"


def main() -> None:
    """CLI エントリポイント.

    ``pyproject.toml`` の ``[project.scripts]`` で
    ``synthpop-jp = "synthpop_jp.cli:main"`` として登録する。
    """
    app()
