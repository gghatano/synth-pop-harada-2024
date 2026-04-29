"""Memory-profile grid orchestrator for SA — Issue #51.

各セル (n_households × max_iters × mode × seed) について、
``synthpop-jp generate`` を子プロセスで起動し、外部から RSS をサンプリングする。
mode ``"full+html"`` の場合は generate 完了後に ``generate_html_report`` を別プロセスで呼ぶ。

OOM ガードで RSS が物理メモリの ``oom_fraction`` を超えたら子プロセスを SIGTERM/SIGKILL する。
結果は ``outputs/peak_rss.csv`` に追記される（resume 可能）。

実行例::

    # smoke (1 セルだけ)
    uv run python experiments/2026-04-29-sa-memory-profile/run.py --smoke

    # フルグリッド
    uv run python experiments/2026-04-29-sa-memory-profile/run.py
"""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml
from make_inputs import generate as gen_inputs
from peak_rss import PeakRSSResult, sample_peak_rss

EXPERIMENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = EXPERIMENT_DIR.parents[1]
VENV_BIN = Path(sys.executable).parent
SYNTHPOP_JP = VENV_BIN / "synthpop-jp"
PYTHON = VENV_BIN / "python"
OUTPUTS_DIR = EXPERIMENT_DIR / "outputs"

DEFAULT_N_HOUSEHOLDS = [1_000, 10_000, 100_000]
DEFAULT_MAX_ITERS = [20_000, 200_000]
DEFAULT_MODES = ["dry-run", "full", "full+html"]
DEFAULT_SEEDS = [1, 2, 3]

CSV_FIELDS = (
    "n_households",
    "max_iters",
    "mode",
    "seed",
    "sa_peak_rss_bytes",
    "sa_elapsed_seconds",
    "sa_oom_killed",
    "sa_exit_code",
    "html_peak_rss_bytes",
    "html_elapsed_seconds",
    "html_oom_killed",
)


def get_physical_memory_bytes() -> int:
    """Return physical memory size in bytes (darwin: sysctl, linux: /proc/meminfo)."""
    if sys.platform == "darwin":
        out = subprocess.check_output(["sysctl", "-n", "hw.memsize"])
        return int(out.strip())
    meminfo = Path("/proc/meminfo")
    if meminfo.exists():
        with meminfo.open() as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) * 1024
    msg = f"Cannot determine physical memory on platform={sys.platform}"
    raise RuntimeError(msg)


def make_html_report_command(output_dir: Path) -> list[str]:
    """Return a Python invocation that renders ``report.html`` from generate outputs."""
    code = (
        "import json;"
        "from pathlib import Path;"
        "import pandas as pd;"
        "from synthpop_jp.reports.html import generate_html_report;"
        f"out = Path({str(output_dir)!r});"
        "data = {"
        '"households": pd.read_csv(out / "synthetic_households.csv"),'
        '"persons": pd.read_csv(out / "synthetic_persons.csv"),'
        '"metrics": json.loads((out / "metrics.json").read_text()),'
        "};"
        'generate_html_report(data, out / "report.html")'
    )
    return [str(PYTHON), "-c", code]


def run_one_cell(
    *,
    n_households: int,
    max_iters: int,
    mode: str,
    seed: int,
    oom_limit_bytes: int,
) -> dict[str, object]:
    """Run one (n_households, max_iters, mode, seed) cell and return a CSV row dict."""
    with tempfile.TemporaryDirectory(prefix="sa_mem_") as tmpdir:
        data_dir = Path(tmpdir) / "data"
        output_dir = Path(tmpdir) / "output"
        gen_inputs(n_households, data_dir)

        config_path = Path(tmpdir) / "config.yaml"
        config = {
            "seed": seed,
            "input_dir": str(data_dir),
            "output_dir": str(output_dir),
            "annealing": {
                "T0": 100.0,
                "alpha": 0.999,
                "max_iters": max_iters,
                "evals_per_agent": 0,
                "target_threshold": 0.0,
                "patience": 0,
            },
        }
        config_path.write_text(yaml.safe_dump(config))

        cmd = [str(SYNTHPOP_JP), "generate", "--config", str(config_path)]
        if mode == "dry-run":
            cmd.append("--dry-run")

        sa_result = sample_peak_rss(cmd, oom_limit_bytes=oom_limit_bytes)

        html_result = PeakRSSResult(
            peak_rss_bytes=0, elapsed_seconds=0.0, oom_killed=False, exit_code=0
        )
        if mode == "full+html" and not sa_result.oom_killed and sa_result.exit_code == 0:
            html_result = sample_peak_rss(
                make_html_report_command(output_dir),
                oom_limit_bytes=oom_limit_bytes,
            )

        return {
            "n_households": n_households,
            "max_iters": max_iters,
            "mode": mode,
            "seed": seed,
            "sa_peak_rss_bytes": sa_result.peak_rss_bytes,
            "sa_elapsed_seconds": round(sa_result.elapsed_seconds, 3),
            "sa_oom_killed": sa_result.oom_killed,
            "sa_exit_code": sa_result.exit_code,
            "html_peak_rss_bytes": html_result.peak_rss_bytes,
            "html_elapsed_seconds": round(html_result.elapsed_seconds, 3),
            "html_oom_killed": html_result.oom_killed,
        }


def load_existing_keys(csv_path: Path) -> set[tuple[int, int, str, int]]:
    """Return tuples (n_households, max_iters, mode, seed) already recorded."""
    if not csv_path.exists():
        return set()
    keys: set[tuple[int, int, str, int]] = set()
    with csv_path.open() as f:
        for row in csv.DictReader(f):
            keys.add(
                (
                    int(row["n_households"]),
                    int(row["max_iters"]),
                    row["mode"],
                    int(row["seed"]),
                )
            )
    return keys


def append_row(csv_path: Path, row: dict[str, object]) -> None:
    """Append a row to ``csv_path``; write header if file is new."""
    new_file = not csv_path.exists()
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerow(row)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the grid orchestrator."""
    parser = argparse.ArgumentParser(description="SA memory-profile grid runner")
    parser.add_argument("--n-households", type=int, nargs="*", default=DEFAULT_N_HOUSEHOLDS)
    parser.add_argument("--max-iters", type=int, nargs="*", default=DEFAULT_MAX_ITERS)
    parser.add_argument("--modes", nargs="*", default=DEFAULT_MODES)
    parser.add_argument("--seeds", type=int, nargs="*", default=DEFAULT_SEEDS)
    parser.add_argument("--output", type=Path, default=OUTPUTS_DIR / "peak_rss.csv")
    parser.add_argument("--oom-fraction", type=float, default=0.7)
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="最小 1 セル (1k × 1000 iter × dry-run × seed=1) のみ実行",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point. Iterate the grid, append results to CSV, skip existing cells."""
    args = parse_args(argv)

    if args.smoke:
        n_list = [1_000]
        iter_list = [1_000]
        mode_list = ["dry-run"]
        seed_list = [1]
    else:
        n_list = args.n_households
        iter_list = args.max_iters
        mode_list = args.modes
        seed_list = args.seeds

    physical = get_physical_memory_bytes()
    oom_limit = int(physical * args.oom_fraction)
    print(f"Physical memory: {physical / 1e9:.1f} GB; OOM limit: {oom_limit / 1e9:.1f} GB")

    existing = load_existing_keys(args.output)
    cells = [
        (n, mi, mo, s) for n in n_list for mi in iter_list for mo in mode_list for s in seed_list
    ]
    skipped = 0
    for n, mi, mo, s in cells:
        if (n, mi, mo, s) in existing:
            skipped += 1
            continue
        print(f"--- n={n}, iter={mi}, mode={mo}, seed={s}")
        row = run_one_cell(
            n_households=n,
            max_iters=mi,
            mode=mo,
            seed=s,
            oom_limit_bytes=oom_limit,
        )
        append_row(args.output, row)
        sa_peak = int(row["sa_peak_rss_bytes"]) / 1e6
        sa_elapsed = float(row["sa_elapsed_seconds"])
        print(f"    SA peak={sa_peak:.0f}MB elapsed={sa_elapsed:.1f}s oom={row['sa_oom_killed']}")

    print(f"Done. Run: {len(cells) - skipped}, Skipped: {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
