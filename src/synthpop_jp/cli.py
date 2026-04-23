"""Command line interface for synthpop-jp.

The CLI exposes six subcommands. All of them report a friendly not-yet-wired
status in Phase 0 and exit non-zero; the concrete behaviour is implemented
during later phases (see ``docs/reviews/action-plan.md`` §3).
"""

from __future__ import annotations

from typing import NoReturn

import typer

app: typer.Typer = typer.Typer(
    name="synthpop-jp",
    help="synthpop-jp: Murata 2017 synthetic population generator + Harada 2024 evaluation.",
    no_args_is_help=True,
    add_completion=False,
)


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
def quickstart() -> None:
    """Run a 10-second sample_case synthesis (implemented in Phase 1)."""
    _not_yet("quickstart", "Phase 1")


@app.command()
def generate(config: str = "configs/base.yaml") -> None:
    """Generate a synthetic population from ``config`` (Phase 1 onward).

    Parameters
    ----------
    config : str
        Path to a YAML configuration file.
    """
    del config
    _not_yet("generate", "Phase 1")


@app.command()
def evaluate(run_dir: str) -> None:
    """Evaluate the synthetic population in ``run_dir`` (Phase 3.5 onward).

    Parameters
    ----------
    run_dir : str
        Directory produced by a previous ``generate`` invocation.
    """
    del run_dir
    _not_yet("evaluate", "Phase 3.5")


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
def validate_config(config: str) -> None:
    """Validate a configuration file without running a full generation.

    Parameters
    ----------
    config : str
        Path to a YAML configuration file.
    """
    del config
    _not_yet("validate-config", "Phase 1")


if __name__ == "__main__":  # pragma: no cover
    app()
