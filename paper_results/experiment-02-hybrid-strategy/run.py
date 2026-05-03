"""paper_results experiment 02 — hybrid strategy (Issue #115 Step 3).

spec §15.2 の Murata 2017 hybrid 戦略実験。固定 seed × 1 つの evals_per_agent
で SA を回し、age-change / age-swap / hybrid の 3 戦略を比較する。

実行モード
----------
- ``--write-expected``: 期待値 CSV を上書き保存する（手動更新時のみ）
- ``--check-tolerance``: 既存 expected との許容幅判定を行う（既定）
- ``--full``: フル設定（n=10 / 1000 世帯）を `expected-full/` で使う
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from paper_results._shared.runner import RunResult, run_one
from paper_results._shared.tolerance_check import compare

if TYPE_CHECKING:
    from collections.abc import Iterable

EXPERIMENT_DIR = Path(__file__).resolve().parent

#: CI 既定設定（plan v1 から調整: 200 hh × 4000 evals 既定が 1 run 約 184 秒の
#: ため、n=3 seeds / 100 世帯 / evals_per_agent=2000 に絞り 9 runs ≈ 4 分）。
CI_SEEDS: tuple[int, ...] = (1, 2, 3)
CI_EVALS_PER_AGENT: int = 2000
CI_HOUSEHOLDS: int = 100

#: フル設定（spec §15.2 / experiment_plan.md 凍結値）。
FULL_SEEDS: tuple[int, ...] = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
FULL_EVALS_PER_AGENT: int = 4000
FULL_HOUSEHOLDS: int = 1000

TRANSITIONS: tuple[str, ...] = ("age_change", "age_swap", "hybrid")


def _run_grid(
    *,
    seeds: Iterable[int],
    evals_per_agent: int,
    n_households: int,
    transitions: Iterable[str],
) -> list[RunResult]:
    """Seeds × transitions の格子点で run_one を回す."""
    results: list[RunResult] = []
    for seed in seeds:
        for transition in transitions:
            print(
                f"[exp02] seed={seed} transition={transition} ...",
                flush=True,
            )
            r = run_one(
                seed=seed,
                transition_kind=transition,
                evals_per_agent=evals_per_agent,
                n_households=n_households,
            )
            print(
                f"[exp02]   best_score={r.best_score:.1f} elapsed={r.elapsed_seconds:.2f}s",
                flush=True,
            )
            results.append(r)
    return results


def _write_best_scores_csv(results: list[RunResult], path: Path) -> None:
    """``best_scores.csv`` を行単位で書き出す."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["seed", "transition", "evals_per_agent", "n_households", "best_score"])
        for r in results:
            w.writerow([r.seed, r.transition_kind, r.evals_per_agent, r.n_households, r.best_score])


def _output_dir(*, full: bool) -> Path:
    """CI 既定なら ``expected/`` 、フルなら ``expected-full/`` を返す."""
    return EXPERIMENT_DIR / ("expected-full" if full else "expected")


def _config(*, full: bool) -> tuple[tuple[int, ...], int, int]:
    """``--full`` の有無で seeds / evals_per_agent / n_households を返す."""
    if full:
        return FULL_SEEDS, FULL_EVALS_PER_AGENT, FULL_HOUSEHOLDS
    return CI_SEEDS, CI_EVALS_PER_AGENT, CI_HOUSEHOLDS


def _write_expected(*, full: bool) -> int:
    """Overwrite expected CSV files (``--write-expected`` モード)."""
    seeds, evals_per_agent, n_households = _config(full=full)
    out_dir = _output_dir(full=full)
    print(
        f"[exp02] writing expected to {out_dir} "
        f"(seeds={list(seeds)}, evals={evals_per_agent}, n_households={n_households})",
        flush=True,
    )
    results = _run_grid(
        seeds=seeds,
        evals_per_agent=evals_per_agent,
        n_households=n_households,
        transitions=TRANSITIONS,
    )
    _write_best_scores_csv(results, out_dir / "best_scores.csv")
    return 0


def _check_tolerance(*, full: bool, summary_out: Path | None) -> int:
    """Compare actual output against expected by tolerance check."""
    seeds, evals_per_agent, n_households = _config(full=full)
    out_dir = _output_dir(full=full)
    if not (out_dir / "best_scores.csv").exists():
        msg = (
            f"expected CSV not found: {out_dir / 'best_scores.csv'}. "
            "Run with --write-expected first."
        )
        print(msg, file=sys.stderr)
        return 2

    print(
        f"[exp02] running grid for tolerance check (full={full})",
        flush=True,
    )
    results = _run_grid(
        seeds=seeds,
        evals_per_agent=evals_per_agent,
        n_households=n_households,
        transitions=TRANSITIONS,
    )

    actual_dir = EXPERIMENT_DIR / "outputs"
    actual_dir.mkdir(parents=True, exist_ok=True)
    actual_best = actual_dir / "best_scores.csv"
    _write_best_scores_csv(results, actual_best)

    report = compare(actual_best, out_dir / "best_scores.csv")
    md = report.to_markdown()
    header = "### exp02 / best_scores.csv\n\n"
    sys.stdout.write(header)
    sys.stdout.write(md)
    if summary_out is not None:
        with summary_out.open("a", encoding="utf-8") as fh:
            fh.write(header)
            fh.write(md)
    return 0 if report.passed else 1


def main(argv: list[str] | None = None) -> int:
    """CLI entry."""
    parser = argparse.ArgumentParser(prog="paper_results.experiment-02")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write-expected", action="store_true")
    mode.add_argument("--check-tolerance", action="store_true")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--summary-out", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.write_expected:
        return _write_expected(full=args.full)
    return _check_tolerance(full=args.full, summary_out=args.summary_out)


if __name__ == "__main__":
    sys.exit(main())
