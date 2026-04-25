"""scripts/check_cadence.py

uncommitted 変更の規模を確認し、閾値超過なら警告して exit 1 する。

Issue #46: Agent が stall せず commit cadence を守る仕組みの物理的強制

使い方:
    uv run python scripts/check_cadence.py
    uv run python scripts/check_cadence.py --worktree /path/to/worktree
    uv run python scripts/check_cadence.py --threshold-files 3 --threshold-lines 100

`make cadence` からも呼べる。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


# デフォルト閾値
DEFAULT_THRESHOLD_FILES = 5
DEFAULT_THRESHOLD_LINES = 200


def _run_git(args: list[str], cwd: Path) -> str:
    """git コマンドを実行してstdoutを返す。失敗したら RuntimeError を上げる."""
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=str(cwd),
    )
    if result.returncode not in (0, 1):
        # git status/diff は変更ありの場合に exit 1 を返すことがある
        raise RuntimeError(
            f"git {' '.join(args)} failed (exit {result.returncode}):\n{result.stderr}"
        )
    return result.stdout


def count_uncommitted_files(worktree: Path) -> int:
    """worktree 内の uncommitted ファイル数を返す。

    tracked の変更（M, D, A など）と untracked (??) の両方を数える。
    """
    output = _run_git(["status", "--short"], worktree)
    lines = [line for line in output.splitlines() if line.strip()]
    return len(lines)


def count_uncommitted_lines(worktree: Path) -> int:
    """worktree 内の uncommitted 追加行数を返す。

    git diff --numstat でステージ済み・未ステージ両方を合計する。
    untracked ファイルは別途 wc -l で数える。
    """
    total_added = 0

    # ステージ済みの差分（--cached）
    staged_output = _run_git(["diff", "--numstat", "--cached"], worktree)
    for line in staged_output.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0].isdigit():
            total_added += int(parts[0])

    # 未ステージの差分
    unstaged_output = _run_git(["diff", "--numstat"], worktree)
    for line in unstaged_output.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0].isdigit():
            total_added += int(parts[0])

    # untracked ファイルの行数
    status_output = _run_git(["status", "--short"], worktree)
    for line in status_output.splitlines():
        if line.startswith("??"):
            # untracked ファイル（スペース区切りでファイル名）
            file_name = line[3:].strip()
            file_path = worktree / file_name
            if file_path.is_file():
                try:
                    content = file_path.read_text(encoding="utf-8", errors="replace")
                    total_added += len(content.splitlines())
                except OSError:
                    pass

    return total_added


def check_cadence(
    worktree: Path,
    threshold_files: int = DEFAULT_THRESHOLD_FILES,
    threshold_lines: int = DEFAULT_THRESHOLD_LINES,
) -> tuple[bool, str]:
    """commit cadence の状態を確認する。

    Returns:
        (ok, message): ok=True なら閾値以内、False なら超過。
    """
    n_files = count_uncommitted_files(worktree)
    n_lines = count_uncommitted_lines(worktree)

    violations: list[str] = []
    if n_files > threshold_files:
        violations.append(
            f"uncommitted files: {n_files} (threshold: {threshold_files})"
        )
    if n_lines > threshold_lines:
        violations.append(
            f"uncommitted lines: {n_lines} (threshold: {threshold_lines})"
        )

    if violations:
        msg_lines = [
            "WARNING: commit cadence threshold exceeded! Please commit now.",
            *[f"  - {v}" for v in violations],
            "",
            "Hint: Run `git add <files> && git commit` to reset the counter.",
            f"  Current: {n_files} files / {n_lines} lines uncommitted",
        ]
        return False, "\n".join(msg_lines)

    return True, f"OK: {n_files} files / {n_lines} lines uncommitted"


def main(argv: list[str] | None = None) -> int:
    """CLI エントリーポイント。exit code を返す（0=OK, 1=NG）."""
    parser = argparse.ArgumentParser(
        description="Check commit cadence: warn if too many uncommitted changes.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python scripts/check_cadence.py
  uv run python scripts/check_cadence.py --worktree /path/to/worktree
  uv run python scripts/check_cadence.py --threshold-files 3 --threshold-lines 100
  make cadence
""",
    )
    parser.add_argument(
        "--worktree",
        type=Path,
        default=Path.cwd(),
        help="Path to the git worktree to check (default: cwd)",
    )
    parser.add_argument(
        "--threshold-files",
        type=int,
        default=DEFAULT_THRESHOLD_FILES,
        help=f"Max uncommitted files before warning (default: {DEFAULT_THRESHOLD_FILES})",
    )
    parser.add_argument(
        "--threshold-lines",
        type=int,
        default=DEFAULT_THRESHOLD_LINES,
        help=f"Max uncommitted lines before warning (default: {DEFAULT_THRESHOLD_LINES})",
    )

    args = parser.parse_args(argv)

    worktree = args.worktree.resolve()
    if not worktree.is_dir():
        print(f"ERROR: worktree path does not exist: {worktree}", file=sys.stderr)
        return 2

    try:
        ok, message = check_cadence(
            worktree=worktree,
            threshold_files=args.threshold_files,
            threshold_lines=args.threshold_lines,
        )
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
