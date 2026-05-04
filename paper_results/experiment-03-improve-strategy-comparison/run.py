"""paper_results experiment 03 — improve loop 3 戦略比較 (Issue #121).

`configs/improve_quick.yaml` を base settings として、rule_based / pareto /
random_search の 3 戦略を同一 seed セット × 同一 n_trials で並べて回し、

- `expected/best_scores.csv`: (seed, strategy) ごとの best trial（composite 最小）
- `expected/strategy_metrics.csv`: 戦略別の seed 平均サマリ

を出力する。CI で 5〜8 分の見込み（3 seeds × 3 戦略 × 5 trials = 45 SA runs）。

実行モード
----------
- ``--write-expected``: 期待値 CSV を上書き保存（手動更新時のみ）
- ``--check-tolerance``: 既存 expected との許容幅判定（既定）
- ``--full``: フル設定（n=10 / n_trials=20 / 1000 世帯）を `expected-full/` で使う
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd
from paper_results._shared.improve_runner import run_improve_for_paper_results
from paper_results._shared.tolerance_check import compare

EXPERIMENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = EXPERIMENT_DIR.parents[1]
BASE_CONFIG = REPO_ROOT / "configs" / "improve_quick.yaml"

#: CI 既定設定（plan 確定値）。45 SA runs ≈ 5〜8 分。
CI_SEEDS: tuple[int, ...] = (1, 2, 3)
CI_N_TRIALS: int = 5
CI_HOUSEHOLDS: int = 100

#: フル設定（spec §15.3 / experiment_plan.md 推奨値の代わりに、当面は
#: **scale-up smoke**（n=5 / n_trials=10 / 500 世帯）で実施する。改善ループ
#: の `evals_per_agent=200` は短いが、500 世帯 × 10 trials × 3 戦略 × 5 seed =
#: 150 SA run になるため、CI 軽量設定の 3 倍強の計算量。論文値の完全再現
#: （n=10 / n_trials=20 / 1000 世帯）は別 Issue で。
FULL_SEEDS: tuple[int, ...] = (1, 2, 3, 4, 5)
FULL_N_TRIALS: int = 10
FULL_HOUSEHOLDS: int = 500

#: 比較する 3 戦略。
STRATEGIES: tuple[str, ...] = ("rule_based", "pareto", "random_search")


# ---------------------------------------------------------------------------
# Grid runner
# ---------------------------------------------------------------------------


def _run_grid(
    *,
    seeds: tuple[int, ...],
    strategies: tuple[str, ...],
    n_trials: int,
    output_root: Path,
    n_households: int,
) -> pd.DataFrame:
    """Seeds × strategies の格子点で improve loop を走らせ、結果を 1 つの DataFrame に."""
    frames: list[pd.DataFrame] = []
    for seed in seeds:
        for strategy in strategies:
            print(
                f"[exp03] seed={seed} strategy={strategy} n_trials={n_trials} "
                f"n_households={n_households} ...",
                flush=True,
            )
            df = run_improve_for_paper_results(
                base_config_path=BASE_CONFIG,
                strategy_name=strategy,
                n_trials=n_trials,
                seed=seed,
                output_root=output_root,
                n_households=n_households,
            )
            print(
                f"[exp03]   trials={len(df)} min_best_score={df['best_score'].min():.1f}",
                flush=True,
            )
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------


def _format_best_scores(all_trials: pd.DataFrame) -> pd.DataFrame:
    """各 (seed, strategy) で composite が最小の trial を best として抽出する."""
    if all_trials.empty:
        return pd.DataFrame(
            columns=[
                "seed",
                "strategy",
                "best_trial_id",
                "best_score",
                "composite",
                "statistical_fit",
                "utility_proxy",
                "privacy_proxy",
            ],
        )
    # composite が最小の行を seed × strategy ごとに取る（同点なら trial_id 最小を採用）
    sorted_df = all_trials.sort_values(by=["seed", "strategy", "composite", "trial_id"])  # type: ignore[arg-type]
    best = sorted_df.groupby(["seed", "strategy"], as_index=False).first()
    out = best.rename(columns={"trial_id": "best_trial_id"})[
        [
            "seed",
            "strategy",
            "best_trial_id",
            "best_score",
            "composite",
            "statistical_fit",
            "utility_proxy",
            "privacy_proxy",
        ]
    ]
    return out.sort_values(by=["seed", "strategy"]).reset_index(drop=True)  # type: ignore[arg-type]


def _format_strategy_metrics(best_df: pd.DataFrame) -> pd.DataFrame:
    """戦略別の seed 平均（best 行を seed 全体で平均）."""
    if best_df.empty:
        return pd.DataFrame(
            columns=[
                "strategy",
                "statistical_fit_mean",
                "utility_proxy_mean",
                "privacy_proxy_mean",
                "composite_mean",
            ],
        )
    grouped = best_df.groupby("strategy", as_index=False).agg(
        statistical_fit_mean=("statistical_fit", "mean"),
        utility_proxy_mean=("utility_proxy", "mean"),
        privacy_proxy_mean=("privacy_proxy", "mean"),
        composite_mean=("composite", "mean"),
    )
    return grouped.sort_values(by="strategy").reset_index(drop=True)  # type: ignore[arg-type]


def _round_for_stable_csv(df: pd.DataFrame) -> pd.DataFrame:
    """CSV を比較しやすいよう数値列を 6 桁に丸める."""
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


def _output_dir(*, full: bool = False) -> Path:
    """Return the directory that holds expected CSVs.

    Parameters
    ----------
    full : bool
        ``True`` のときフル設定用の ``expected-full/`` を返す。
    """
    return EXPERIMENT_DIR / ("expected-full" if full else "expected")


def _config(*, full: bool) -> tuple[tuple[int, ...], int, int]:
    """``--full`` の有無で seeds / n_trials / n_households を返す."""
    if full:
        return FULL_SEEDS, FULL_N_TRIALS, FULL_HOUSEHOLDS
    return CI_SEEDS, CI_N_TRIALS, CI_HOUSEHOLDS


def _do_run(*, write: bool, full: bool, summary_out: Path | None) -> int:
    out_dir = _output_dir(full=full)
    expected_best = out_dir / "best_scores.csv"
    expected_metrics = out_dir / "strategy_metrics.csv"

    if not write and not expected_best.exists():
        msg = f"expected CSV not found: {expected_best}. Run with --write-expected first."
        print(msg, file=sys.stderr)
        return 2

    seeds, n_trials, n_households = _config(full=full)
    with TemporaryDirectory() as tmp:
        tmp_root = Path(tmp) / "improve"
        all_trials = _run_grid(
            seeds=seeds,
            strategies=STRATEGIES,
            n_trials=n_trials,
            output_root=tmp_root,
            n_households=n_households,
        )

    best_df = _format_best_scores(all_trials)
    metrics_df = _format_strategy_metrics(best_df)

    if write:
        _write_csv(best_df, expected_best)
        _write_csv(metrics_df, expected_metrics)
        print(f"[exp03] wrote {expected_best} ({len(best_df)} rows)", flush=True)
        print(f"[exp03] wrote {expected_metrics} ({len(metrics_df)} rows)", flush=True)
        return 0

    actual_dir = EXPERIMENT_DIR / "outputs"
    actual_dir.mkdir(parents=True, exist_ok=True)
    actual_best = actual_dir / "best_scores.csv"
    actual_metrics = actual_dir / "strategy_metrics.csv"
    _write_csv(best_df, actual_best)
    _write_csv(metrics_df, actual_metrics)

    failed = False
    for actual, name in (
        (actual_best, "best_scores.csv"),
        (actual_metrics, "strategy_metrics.csv"),
    ):
        report = compare(actual, out_dir / name)
        md = report.to_markdown()
        header = f"### exp03 / {name}\n\n"
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
    parser = argparse.ArgumentParser(prog="paper_results.experiment-03")
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
        help="use full config (n=10 seeds / n_trials=20 / 1000 households)",
    )
    parser.add_argument(
        "--summary-out",
        type=Path,
        default=None,
        help="optional path to append the Markdown report (e.g. $GITHUB_STEP_SUMMARY)",
    )
    args = parser.parse_args(argv)

    return _do_run(write=args.write_expected, full=args.full, summary_out=args.summary_out)


if __name__ == "__main__":
    sys.exit(main())
