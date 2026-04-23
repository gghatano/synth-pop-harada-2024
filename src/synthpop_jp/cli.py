"""Command line interface for synthpop-jp.

The CLI exposes six subcommands. All of them raise :class:`NotImplementedError`
in Phase 0; the concrete behaviour is implemented during later phases
(see ``docs/reviews/action-plan.md`` §3).
"""

from __future__ import annotations

import typer

app: typer.Typer = typer.Typer(
    name="synthpop-jp",
    help="synthpop-jp: Murata 2017 synthetic population generator + Harada 2024 evaluation.",
    no_args_is_help=True,
    add_completion=False,
)


@app.command()
def quickstart() -> None:
    """Run a 10-second sample_case synthesis (implemented in Phase 1)."""
    raise NotImplementedError("quickstart will be implemented in Phase 1.")


@app.command()
def generate(config: str = "configs/base.yaml") -> None:
    """Generate a synthetic population from ``config`` (Phase 1 onward).

    Parameters
    ----------
    config : str
        Path to a YAML configuration file.
    """
    raise NotImplementedError("generate will be implemented in Phase 1.")


@app.command()
def evaluate(run_dir: str) -> None:
    """Evaluate the synthetic population in ``run_dir`` (Phase 3.5 onward).

    Parameters
    ----------
    run_dir : str
        Directory produced by a previous ``generate`` invocation.
    """
    raise NotImplementedError("evaluate will be implemented in Phase 3.5.")


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
    raise NotImplementedError("improve will be implemented in Phase 5.")


@app.command()
def compare(experiment: str) -> None:
    """Compare multiple runs of an experiment (Phase 3b onward).

    Parameters
    ----------
    experiment : str
        Path to an experiment configuration.
    """
    raise NotImplementedError("compare will be implemented in Phase 3b.")


@app.command("validate-config")
def validate_config(config: str) -> None:
    """Validate a configuration file without running a full generation.

    Parameters
    ----------
    config : str
        Path to a YAML configuration file.
    """
    raise NotImplementedError("validate-config will be implemented in Phase 1.")


if __name__ == "__main__":  # pragma: no cover
    app()
