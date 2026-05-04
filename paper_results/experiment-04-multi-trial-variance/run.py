"""paper_results experiment 04 — 複数候補ばらつき (Issue #121).

`configs/improve_quick.yaml` を base settings として、rule_based 戦略を 1 つに
固定し 5 seeds × n_trials=5 の合計 25 試行を回す。各 trial の 4 指標
(best_score / statistical_fit / utility_proxy / privacy_proxy) を
`expected/trial_metrics.csv` に固定し、指標ごとの mean / std / CV と
bootstrap percentile CI を `expected/variance_summary.csv` にまとめる。

実行モード
----------
- ``--write-expected``: 期待値 CSV を上書き保存（手動更新時のみ）
- ``--check-tolerance``: 既存 expected との許容幅判定（既定）
"""

from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd
from paper_results._shared.improve_runner import run_improve_for_paper_results
from paper_results._shared.tolerance_check import compare

from synthpop_jp.compare.stats import bootstrap_ci

EXPERIMENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = EXPERIMENT_DIR.parents[1]
BASE_CONFIG = REPO_ROOT / "configs" / "improve_quick.yaml"

#: CI 既定設定（plan 確定値）。25 SA runs ≈ 2〜3 分。
CI_SEEDS: tuple[int, ...] = (1, 2, 3, 4, 5)
CI_N_TRIALS: int = 5

#: 戦略は rule_based 固定。
STRATEGY: str = "rule_based"

#: bootstrap CI 設定。
BOOTSTRAP_N: int = 2000
BOOTSTRAP_CONFIDENCE: float = 0.95
BOOTSTRAP_RNG_SEED: int = 42

#: 集計対象の 4 指標。
METRICS: tuple[str, ...] = (
    "best_score",
    "statistical_fit",
    "utility_proxy",
    "privacy_proxy",
)


# ---------------------------------------------------------------------------
# Grid runner
# ---------------------------------------------------------------------------


def _run_grid(
    *,
    seeds: tuple[int, ...],
    n_trials: int,
    output_root: Path,
) -> pd.DataFrame:
    """Seeds × trials の格子点で improve loop を走らせ、結果を 1 つの DataFrame に."""
    frames: list[pd.DataFrame] = []
    for seed in seeds:
        print(
            f"[exp04] seed={seed} strategy={STRATEGY} n_trials={n_trials} ...",
            flush=True,
        )
        df = run_improve_for_paper_results(
            base_config_path=BASE_CONFIG,
            strategy_name=STRATEGY,
            n_trials=n_trials,
            seed=seed,
            output_root=output_root,
        )
        print(
            f"[exp04]   trials={len(df)} min_best_score={df['best_score'].min():.1f}",
            flush=True,
        )
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------


def _format_trial_metrics(all_trials: pd.DataFrame) -> pd.DataFrame:
    """trial_metrics.csv 用の DataFrame.

    25 行（seed × trial_id を昇順）。列は ``seed, trial_id, best_score,
    statistical_fit, utility_proxy, privacy_proxy``。
    """
    if all_trials.empty:
        return pd.DataFrame(columns=("seed", "trial_id", *METRICS))
    out = all_trials[
        ["seed", "trial_id", "best_score", "statistical_fit", "utility_proxy", "privacy_proxy"]
    ].copy()
    return out.sort_values(by=["seed", "trial_id"]).reset_index(drop=True)  # type: ignore[arg-type]


def _compute_variance_summary(trial_metrics: pd.DataFrame) -> pd.DataFrame:
    """各指標の mean / std / CV / bootstrap CI を 1 つの DataFrame に."""
    rng = np.random.default_rng(BOOTSTRAP_RNG_SEED)
    rows: list[dict[str, float | str]] = []
    for metric in METRICS:
        values = trial_metrics[metric].astype(float).tolist()
        if not values:
            rows.append(
                {
                    "metric": metric,
                    "seed_mean": float("nan"),
                    "seed_std": float("nan"),
                    "seed_cv": float("nan"),
                    "bootstrap_ci_low": float("nan"),
                    "bootstrap_ci_high": float("nan"),
                },
            )
            continue
        mean = statistics.mean(values)
        # n=1 では std を 0 とする（決定論的に扱う）
        std = statistics.stdev(values) if len(values) >= 2 else 0.0
        cv = (std / mean) if abs(mean) > 1e-12 else 0.0
        ci_low, ci_high = bootstrap_ci(
            values=values,
            n_bootstrap=BOOTSTRAP_N,
            confidence=BOOTSTRAP_CONFIDENCE,
            rng=rng,
        )
        rows.append(
            {
                "metric": metric,
                "seed_mean": float(mean),
                "seed_std": float(std),
                "seed_cv": float(cv),
                "bootstrap_ci_low": float(ci_low),
                "bootstrap_ci_high": float(ci_high),
            },
        )
    return pd.DataFrame(rows)


def _round_for_stable_csv(df: pd.DataFrame) -> pd.DataFrame:
    """CSV 比較しやすいよう数値列を 6 桁に丸める."""
    df = df.copy()
    for col in df.columns:
        if df[col].dtype.kind == "f":
            df[col] = df[col].round(6)
    return df


def _write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _round_for_stable_csv(df).to_csv(path, index=False)


# ---------------------------------------------------------------------------
# CLI modes
# ---------------------------------------------------------------------------


def _output_dir() -> Path:
    return EXPERIMENT_DIR / "expected"


def _do_run(*, write: bool, summary_out: Path | None) -> int:
    out_dir = _output_dir()
    expected_trials = out_dir / "trial_metrics.csv"
    expected_summary = out_dir / "variance_summary.csv"

    if not write and not expected_trials.exists():
        msg = f"expected CSV not found: {expected_trials}. Run with --write-expected first."
        print(msg, file=sys.stderr)
        return 2

    with TemporaryDirectory() as tmp:
        tmp_root = Path(tmp) / "improve"
        all_trials = _run_grid(
            seeds=CI_SEEDS,
            n_trials=CI_N_TRIALS,
            output_root=tmp_root,
        )

    trials_df = _format_trial_metrics(all_trials)
    summary_df = _compute_variance_summary(trials_df)

    if write:
        _write_csv(trials_df, expected_trials)
        _write_csv(summary_df, expected_summary)
        print(f"[exp04] wrote {expected_trials} ({len(trials_df)} rows)", flush=True)
        print(f"[exp04] wrote {expected_summary} ({len(summary_df)} rows)", flush=True)
        return 0

    actual_dir = EXPERIMENT_DIR / "outputs"
    actual_dir.mkdir(parents=True, exist_ok=True)
    actual_trials = actual_dir / "trial_metrics.csv"
    actual_summary = actual_dir / "variance_summary.csv"
    _write_csv(trials_df, actual_trials)
    _write_csv(summary_df, actual_summary)

    failed = False
    for actual, name in (
        (actual_trials, "trial_metrics.csv"),
        (actual_summary, "variance_summary.csv"),
    ):
        report = compare(actual, out_dir / name)
        md = report.to_markdown()
        header = f"### exp04 / {name}\n\n"
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
    parser = argparse.ArgumentParser(prog="paper_results.experiment-04")
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
        "--summary-out",
        type=Path,
        default=None,
        help="optional path to append the Markdown report (e.g. $GITHUB_STEP_SUMMARY)",
    )
    args = parser.parse_args(argv)

    return _do_run(write=args.write_expected, summary_out=args.summary_out)


if __name__ == "__main__":
    sys.exit(main())
