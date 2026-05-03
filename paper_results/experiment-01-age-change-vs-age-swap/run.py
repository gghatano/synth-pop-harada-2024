"""paper_results experiment 01 — age-change vs age-swap (Issue #115 Step 2).

spec §15.1 の Murata 2017 再現実験。固定 seed × evals_per_agent 水準 × 2 戦略
で SA を回し、`best_scores.csv` と `stat_l1.csv` を `expected/`（CI 既定）か
`expected-full/`（フル設定、`workflow_dispatch` 限定）に書き出す。

実行モード
----------
- ``--write-expected``: 期待値 CSV を上書き保存する（手動更新時のみ使う）
- ``--check-tolerance``: 既存 expected との許容幅判定を行う（既定）
- ``--full``: フル設定（n=10 / 5 水準 / 1000 世帯）を `expected-full/` に対して使う

詳細は ``paper_results/README.md`` と本ディレクトリの ``INPUT.md`` を参照。
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

#: CI 既定設定（〜10 分以内、experiment_plan.md 確定値）。
#: 実機計測で 200 hh × 4000 evals (age_swap) が 1 run 184 秒、500 hh × 1000
#: evals が 30 秒だったため、CI 予算 10 分内に収めるべく n=3 seeds /
#: 100 世帯 / evals 2 水準 (500, 2000) に絞る（plan v1 の n=5/3水準/500hh から
#: 調整、exp01+exp02 合算で約 8 分）。フル設定は ``--full`` 経由で別途検証する。
CI_SEEDS: tuple[int, ...] = (1, 2, 3)
CI_EVALS: tuple[int, ...] = (500, 2000)
CI_HOUSEHOLDS: int = 100

#: フル設定（workflow_dispatch + ローカル `make paper-results-full` 専用）。
#: spec §15.1 / experiment_plan.md の凍結値（n=10 / 5 水準 / 1000 世帯）。
FULL_SEEDS: tuple[int, ...] = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
FULL_EVALS: tuple[int, ...] = (1000, 2000, 4000, 8000, 16000)
FULL_HOUSEHOLDS: int = 1000

TRANSITIONS: tuple[str, ...] = ("age_change", "age_swap")


def _run_grid(
    *,
    seeds: Iterable[int],
    evals: Iterable[int],
    n_households: int,
    transitions: Iterable[str],
) -> list[RunResult]:
    """seeds × evals × transitions の格子点で run_one を回す."""
    results: list[RunResult] = []
    for seed in seeds:
        for evals_per_agent in evals:
            for transition in transitions:
                print(
                    f"[exp01] seed={seed} evals={evals_per_agent} "
                    f"transition={transition} ...",
                    flush=True,
                )
                r = run_one(
                    seed=seed,
                    transition_kind=transition,
                    evals_per_agent=evals_per_agent,
                    n_households=n_households,
                )
                print(
                    f"[exp01]   best_score={r.best_score:.1f} "
                    f"elapsed={r.elapsed_seconds:.2f}s",
                    flush=True,
                )
                results.append(r)
    return results


def _write_best_scores_csv(results: list[RunResult], path: Path) -> None:
    """``best_scores.csv`` を行単位で書き出す.

    列: seed, transition, evals_per_agent, n_households, best_score
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["seed", "transition", "evals_per_agent", "n_households", "best_score"])
        for r in results:
            w.writerow(
                [r.seed, r.transition_kind, r.evals_per_agent, r.n_households, r.best_score]
            )


def _write_stat_l1_csv(results: list[RunResult], path: Path) -> None:
    """``stat_l1.csv`` を行単位で書き出す.

    列: seed, transition, evals_per_agent, stat_id, l1
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["seed", "transition", "evals_per_agent", "stat_id", "l1"])
        for r in results:
            for stat_id, l1 in r.stat_l1.items():
                w.writerow([r.seed, r.transition_kind, r.evals_per_agent, stat_id, l1])


def _output_dir(*, full: bool) -> Path:
    """CI 既定なら ``expected/`` 、フルなら ``expected-full/`` を返す."""
    return EXPERIMENT_DIR / ("expected-full" if full else "expected")


def _config(*, full: bool) -> tuple[tuple[int, ...], tuple[int, ...], int]:
    """``--full`` の有無で seeds / evals / n_households を返す."""
    if full:
        return FULL_SEEDS, FULL_EVALS, FULL_HOUSEHOLDS
    return CI_SEEDS, CI_EVALS, CI_HOUSEHOLDS


def _write_expected(*, full: bool) -> int:
    """expected 系 CSV を上書きする（``--write-expected`` モード）."""
    seeds, evals, n_households = _config(full=full)
    out_dir = _output_dir(full=full)
    print(
        f"[exp01] writing expected to {out_dir} "
        f"(seeds={list(seeds)}, evals={list(evals)}, n_households={n_households})",
        flush=True,
    )
    results = _run_grid(
        seeds=seeds,
        evals=evals,
        n_households=n_households,
        transitions=TRANSITIONS,
    )
    _write_best_scores_csv(results, out_dir / "best_scores.csv")
    _write_stat_l1_csv(results, out_dir / "stat_l1.csv")
    return 0


def _check_tolerance(*, full: bool, summary_out: Path | None) -> int:
    """tempdir に actual を書き出し、expected と許容幅判定で比較する."""
    seeds, evals, n_households = _config(full=full)
    out_dir = _output_dir(full=full)
    if not (out_dir / "best_scores.csv").exists():
        msg = (
            f"expected CSV not found: {out_dir / 'best_scores.csv'}. "
            "Run with --write-expected first."
        )
        print(msg, file=sys.stderr)
        return 2

    print(
        f"[exp01] running grid for tolerance check (full={full}, n_households={n_households})",
        flush=True,
    )
    results = _run_grid(
        seeds=seeds,
        evals=evals,
        n_households=n_households,
        transitions=TRANSITIONS,
    )

    actual_dir = EXPERIMENT_DIR / "outputs"
    actual_dir.mkdir(parents=True, exist_ok=True)
    actual_best = actual_dir / "best_scores.csv"
    actual_stat = actual_dir / "stat_l1.csv"
    _write_best_scores_csv(results, actual_best)
    _write_stat_l1_csv(results, actual_stat)

    failed = False
    for actual, name in ((actual_best, "best_scores.csv"), (actual_stat, "stat_l1.csv")):
        report = compare(actual, out_dir / name)
        md = report.to_markdown()
        header = f"### exp01 / {name}\n\n"
        sys.stdout.write(header)
        sys.stdout.write(md)
        if summary_out is not None:
            with summary_out.open("a", encoding="utf-8") as fh:
                fh.write(header)
                fh.write(md)
        if not report.passed:
            failed = True
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry."""
    parser = argparse.ArgumentParser(prog="paper_results.experiment-01")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--write-expected",
        action="store_true",
        help="overwrite expected CSV (manual update only)",
    )
    mode.add_argument(
        "--check-tolerance",
        action="store_true",
        help="run grid and compare against expected/ (default behaviour)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="use full config (n=10 / 5 levels / 1000 households)",
    )
    parser.add_argument(
        "--summary-out",
        type=Path,
        default=None,
        help="optional path to append the Markdown report (e.g. $GITHUB_STEP_SUMMARY)",
    )
    args = parser.parse_args(argv)

    if args.write_expected:
        return _write_expected(full=args.full)
    return _check_tolerance(full=args.full, summary_out=args.summary_out)


if __name__ == "__main__":
    sys.exit(main())
