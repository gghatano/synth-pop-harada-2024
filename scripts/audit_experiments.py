"""Audit experiments/ directories for reproducibility metadata (Issue #115 Step 5).

各 ``experiments/<slug>/`` ディレクトリについて以下をチェックする:

- ``INPUT.md`` が存在し、``seed:`` / ``commit_sha:`` / ``uv_lock_sha256:`` の
  3 行をすべて含むこと（spec §19.3 指紋）
- ``WEIGHT.md`` が存在し、``light`` または ``heavy`` の 1 行であること
- ``run.py`` が存在すること

不足項目があれば標準出力に表で出し、終了コード 1 を返す。
すべて満たしていれば終了コード 0。

CLI:
    uv run python scripts/audit_experiments.py [experiments_root]
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

#: INPUT.md に必ず登場すべき key 群（spec §19.3 + 既存運用との整合）。
REQUIRED_INPUT_KEYS: tuple[str, ...] = (
    "seed",
    "commit_sha",
    "uv_lock_sha256",
)

#: WEIGHT.md に許容する 1 行の値。
VALID_WEIGHTS: tuple[str, ...] = ("light", "heavy")


@dataclass
class AuditReport:
    """1 つの実験ディレクトリの監査結果.

    Attributes
    ----------
    directory : Path
        対象ディレクトリ。
    passed : bool
        すべてのチェックを通ったか。
    missing : list[str]
        不足項目の人間向けメッセージ。
    """

    directory: Path
    passed: bool = True
    missing: list[str] = field(default_factory=lambda: [])


def audit_directory(exp_dir: Path) -> AuditReport:
    """1 つの ``experiments/<slug>/`` ディレクトリを監査する.

    Parameters
    ----------
    exp_dir : Path
        対象ディレクトリ。

    Returns
    -------
    AuditReport
        ``passed`` と不足項目のリスト。
    """
    report = AuditReport(directory=exp_dir)

    # INPUT.md
    input_md = exp_dir / "INPUT.md"
    if not input_md.exists():
        report.missing.append(f"INPUT.md missing in {exp_dir.name}")
    else:
        text = input_md.read_text(encoding="utf-8").lower()
        for key in REQUIRED_INPUT_KEYS:
            # `seed:` / `commit_sha:` / `uv_lock_sha256:` のいずれかの形が含まれているか
            if f"{key}:" not in text:
                report.missing.append(
                    f"INPUT.md in {exp_dir.name} is missing required key '{key}:'"
                )

    # WEIGHT.md
    weight_md = exp_dir / "WEIGHT.md"
    if not weight_md.exists():
        report.missing.append(f"WEIGHT.md missing in {exp_dir.name}")
    else:
        first_line = weight_md.read_text(encoding="utf-8").splitlines()[0:1]
        token = first_line[0].strip() if first_line else ""
        if token not in VALID_WEIGHTS:
            report.missing.append(
                f"WEIGHT.md in {exp_dir.name} must be one of {VALID_WEIGHTS} (got {token!r})"
            )

    # run.py
    if not (exp_dir / "run.py").exists():
        report.missing.append(f"run.py missing in {exp_dir.name}")

    report.passed = not report.missing
    return report


def _emit_table(reports: list[AuditReport]) -> None:
    """監査結果を Markdown 表で標準出力に出す."""
    sys.stdout.write("| directory | status | missing |\n")
    sys.stdout.write("|---|:---:|---|\n")
    for r in reports:
        status = "PASS" if r.passed else "FAIL"
        missing = "; ".join(r.missing) if r.missing else "-"
        sys.stdout.write(f"| {r.directory.name} | {status} | {missing} |\n")


def main(argv: list[str] | None = None) -> int:
    """CLI entry: ``python scripts/audit_experiments.py [experiments_root]``.

    Parameters
    ----------
    argv : list[str] | None
        コマンドライン引数。``None`` のとき ``sys.argv[1:]``。

    Returns
    -------
    int
        0 = 全 PASS、1 = 1 件以上 FAIL、2 = usage / I/O エラー。
    """
    parser = argparse.ArgumentParser(prog="audit_experiments")
    default_root = Path(__file__).resolve().parents[1] / "experiments"
    parser.add_argument(
        "experiments_root",
        type=Path,
        nargs="?",
        default=default_root,
        help="path to experiments/ root (default: <repo>/experiments)",
    )
    args = parser.parse_args(argv)

    root = args.experiments_root
    if not root.is_dir():
        sys.stderr.write(f"experiments root not found: {root}\n")
        return 2

    reports: list[AuditReport] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        if child.name.startswith("."):
            continue
        reports.append(audit_directory(child))

    _emit_table(reports)
    return 0 if all(r.passed for r in reports) else 1


if __name__ == "__main__":
    sys.exit(main())
