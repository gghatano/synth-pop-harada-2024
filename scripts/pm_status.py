"""PM status dashboard — 並列 Agent の進捗を 1 コマンドで把握する.

使い方::

    uv run python scripts/pm_status.py
    uv run python scripts/pm_status.py --phase 2 --stale-minutes 15
    uv run python scripts/pm_status.py --json
    make pm
    make pm ARGS="--phase 2"
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import timedelta
from pathlib import Path
from typing import Literal

from rich.console import Console
from rich.table import Table

# ---------------------------------------------------------------------------
# データ構造
# ---------------------------------------------------------------------------


@dataclass
class WorktreeInfo:
    """1 つの git worktree に関するメタ情報."""

    path: str
    branch: str
    commits_ahead: int
    uncommitted_count: int
    last_commit_age: timedelta
    plan_comment_exists: bool
    progress_comment_count: int
    pr_number: int | None
    pr_state: str | None
    # Issue #52: experiments/*/WEIGHT.md の集約結果（"heavy" / "light" / None）
    weight: str | None = None


@dataclass
class IssueInfo:
    """1 つの GitHub Issue に関するメタ情報."""

    number: int
    title: str
    state: str
    blocked_by: list[int]
    assigned_worktree: str | None


@dataclass
class PRInfo:
    """1 つの GitHub PR に関するメタ情報."""

    number: int
    title: str
    merged_at: str


# ---------------------------------------------------------------------------
# 外部コール層（テストでモック差し替え可能）
# ---------------------------------------------------------------------------


def _run_cmd(args: list[str], cwd: str | None = None) -> str:
    """サブプロセスを実行して stdout を返す.

    失敗時は RuntimeError を raise する。
    """
    result = subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=15,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Command {args!r} failed: {result.stderr.strip()}")
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# worktree 情報収集
# ---------------------------------------------------------------------------


def _detect_weight(worktree_path: str) -> str | None:
    """Aggregate experiments/*/WEIGHT.md within a worktree to a single tier.

    Issue #52: PM が「この worktree は重実験を含むか」を 1 値で判断するための関数。
    max-rule で集約する: heavy が 1 つでもあれば "heavy"、全て light なら "light"、
    どれも無ければ None。

    Parameters
    ----------
    worktree_path : str
        worktree のルートパス。

    Returns
    -------
    str | None
        "heavy" / "light" / None。
    """
    exp_dir = Path(worktree_path) / "experiments"
    if not exp_dir.is_dir():
        return None

    weights: list[str] = []
    for weight_file in exp_dir.glob("*/WEIGHT.md"):
        try:
            content = weight_file.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if content not in {"light", "heavy"}:
            logger = logging.getLogger(__name__)
            logger.warning(
                "Unknown WEIGHT.md value %r in %s (expected 'light' or 'heavy')",
                content,
                weight_file,
            )
            continue
        weights.append(content)

    if not weights:
        return None
    if "heavy" in weights:
        return "heavy"
    return "light"


def _get_issue_comment_counts(branch: str) -> tuple[bool, int]:
    """ブランチ名から Issue 番号を推定し、plan/progress コメント数を返す.

    ブランチ名 feature/<N>-<keyword> から Issue #N を推定する。
    失敗した場合は (False, 0) を返す。
    """
    # feature/<N>-<keyword> or feature-<N>-<keyword> から N を抽出
    parts = branch.replace("feature/", "").replace("feature-", "")
    try:
        issue_num = int(parts.split("-")[0])
    except (ValueError, IndexError):
        return False, 0

    try:
        output = _run_cmd(
            [
                "gh",
                "issue",
                "view",
                str(issue_num),
                "--json",
                "comments",
            ]
        )
        data = json.loads(output)
        comments: list[dict[str, object]] = data.get("comments", [])
        plan_exists = any(
            "plan" in str(c.get("body", "")).lower() or "実装計画" in str(c.get("body", ""))
            for c in comments
        )
        progress_count = len(comments)
        return plan_exists, progress_count
    except (RuntimeError, json.JSONDecodeError, KeyError):
        return False, 0


def _get_pr_for_branch(branch: str) -> tuple[int | None, str | None]:
    """ブランチに対応する PR 番号と状態を取得する.

    見つからなければ (None, None) を返す。
    """
    try:
        output = _run_cmd(
            [
                "gh",
                "pr",
                "list",
                "--head",
                branch,
                "--json",
                "number,state",
            ]
        )
        prs: list[dict[str, object]] = json.loads(output)
        if prs:
            pr = prs[0]
            return int(str(pr["number"])), str(pr["state"])
        return None, None
    except (RuntimeError, json.JSONDecodeError, KeyError, ValueError):
        return None, None


def _collect_single_worktree(path: str, branch: str) -> WorktreeInfo | None:
    """1 つの worktree の情報を収集する.

    失敗した場合は None を返す。
    """
    try:
        # origin/develop からの commits ahead
        try:
            ahead_str = _run_cmd(["git", "-C", path, "rev-list", "--count", "origin/develop..HEAD"])
            commits_ahead = int(ahead_str) if ahead_str else 0
        except (RuntimeError, ValueError):
            commits_ahead = 0

        # uncommitted files count
        try:
            status_output = _run_cmd(["git", "-C", path, "status", "--porcelain"])
            uncommitted_count = len([line for line in status_output.splitlines() if line.strip()])
        except RuntimeError:
            uncommitted_count = 0

        # last commit timestamp
        try:
            ts_str = _run_cmd(["git", "-C", path, "log", "-1", "--format=%ct"])
            ts = int(ts_str) if ts_str else int(time.time())
            last_commit_age = timedelta(seconds=int(time.time()) - ts)
        except (RuntimeError, ValueError):
            last_commit_age = timedelta(seconds=0)

        # Issue コメント情報
        plan_exists, progress_count = _get_issue_comment_counts(branch)

        # PR 情報
        pr_number, pr_state = _get_pr_for_branch(branch)

        return WorktreeInfo(
            path=path,
            branch=branch,
            commits_ahead=commits_ahead,
            uncommitted_count=uncommitted_count,
            last_commit_age=last_commit_age,
            plan_comment_exists=plan_exists,
            progress_comment_count=progress_count,
            pr_number=pr_number,
            pr_state=pr_state,
            weight=_detect_weight(path),
        )
    except Exception:
        return None


def collect_worktree_info() -> list[WorktreeInfo]:
    """全 git worktree を一覧し、feature ブランチのみ情報を収集して返す."""
    try:
        output = _run_cmd(["git", "worktree", "list"])
    except RuntimeError:
        return []

    feature_worktrees: list[tuple[str, str]] = []
    for line in output.splitlines():
        line_parts = line.split()
        if len(line_parts) < 3:
            continue
        path = line_parts[0]
        branch_raw = line_parts[2].strip("[]")
        # main / develop / detached は除外
        if branch_raw in ("main", "develop", "(detached)") or branch_raw.startswith("HEAD"):
            continue
        feature_worktrees.append((path, branch_raw))

    if not feature_worktrees:
        return []

    results: list[WorktreeInfo] = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(_collect_single_worktree, path, branch): (path, branch)
            for path, branch in feature_worktrees
        }
        for future in as_completed(futures):
            info = future.result()
            if info is not None:
                results.append(info)

    return sorted(results, key=lambda x: x.path)


# ---------------------------------------------------------------------------
# Issue 情報収集
# ---------------------------------------------------------------------------


def _parse_blocked_by(body: str) -> list[int]:
    """Issue 本文から blocked_by の Issue 番号リストを抽出する."""
    blocked: list[int] = []
    for line in body.splitlines():
        if "blocked" in line.lower() or "depends" in line.lower():
            nums = re.findall(r"#(\d+)", line)
            blocked.extend(int(n) for n in nums)
    return blocked


def collect_open_issues(phase: int | None) -> list[IssueInfo]:
    """Open な Issue 一覧を取得する.

    phase 指定があればラベルでフィルタする。
    """
    try:
        args = [
            "gh",
            "issue",
            "list",
            "--state",
            "open",
            "--json",
            "number,title,state,labels,body",
            "--limit",
            "100",
        ]
        if phase is not None:
            args += ["--label", f"phase-{phase}"]
        output = _run_cmd(args)
        issues_data: list[dict[str, object]] = json.loads(output)
    except (RuntimeError, json.JSONDecodeError):
        return []

    results: list[IssueInfo] = []
    for issue in issues_data:
        body = str(issue.get("body", "") or "")
        blocked_by = _parse_blocked_by(body)
        results.append(
            IssueInfo(
                number=int(str(issue["number"])),
                title=str(issue.get("title", "")),
                state=str(issue.get("state", "OPEN")),
                blocked_by=blocked_by,
                # worktree 情報と突き合わせは呼び出し元で行う
                assigned_worktree=None,
            )
        )

    return results


# ---------------------------------------------------------------------------
# PR 情報収集
# ---------------------------------------------------------------------------


def collect_recent_merged_prs(limit: int) -> list[PRInfo]:
    """最近 merged された PR を limit 件取得して返す."""
    try:
        output = _run_cmd(
            [
                "gh",
                "pr",
                "list",
                "--state",
                "merged",
                "--limit",
                str(limit),
                "--json",
                "number,title,mergedAt",
            ]
        )
        prs_data: list[dict[str, object]] = json.loads(output)
    except (RuntimeError, json.JSONDecodeError):
        return []

    return [
        PRInfo(
            number=int(str(pr["number"])),
            title=str(pr.get("title", "")),
            merged_at=str(pr.get("mergedAt", "")),
        )
        for pr in prs_data
    ]


# ---------------------------------------------------------------------------
# stale 判定
# ---------------------------------------------------------------------------


def determine_staleness(
    last_commit_age: timedelta, stale_minutes: int
) -> Literal["ok", "warn", "danger"]:
    """最終 commit からの経過時間で stale 状態を判定する.

    Parameters
    ----------
    last_commit_age:
        最終 commit からの経過時間。
    stale_minutes:
        警告閾値（分）。これ以上経過すると warn、2 倍以上で danger。

    Returns
    -------
    "ok" | "warn" | "danger"
    """
    elapsed_minutes = last_commit_age.total_seconds() / 60
    if elapsed_minutes >= stale_minutes * 2:
        return "danger"
    if elapsed_minutes >= stale_minutes:
        return "warn"
    return "ok"


# ---------------------------------------------------------------------------
# rich テーブル組み立て
# ---------------------------------------------------------------------------

_STALE_MARK = {"ok": "", "warn": "🟡", "danger": "🔴"}
_UNCOMMITTED_MARK = "🟠"


def _format_age(age: timedelta) -> str:
    """経過時間を短い文字列に変換する."""
    total_seconds = int(age.total_seconds())
    if total_seconds < 60:
        return f"{total_seconds}s"
    minutes = total_seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    remaining = minutes % 60
    return f"{hours}h{remaining}m"


def _shorten_path(path: str) -> str:
    """Worktree パスを gitworktree/ 以降の部分に短縮する."""
    if "/gitworktree/" in path:
        return path.split("/gitworktree/")[-1]
    return path


def build_worktree_table(infos: list[WorktreeInfo], stale_minutes: int) -> Table:
    """WorktreeInfo リストから rich Table を組み立てる（テーブル A）."""
    table = Table(
        title="Active Worktrees",
        show_lines=True,
        expand=False,
    )
    # 8 列固定
    table.add_column("worktree", style="cyan", no_wrap=False, max_width=35)
    table.add_column("branch", style="green", no_wrap=False, max_width=30)
    table.add_column("ahead", justify="right")
    table.add_column("uncommitted", justify="right")
    table.add_column("last commit", justify="right")
    table.add_column("plan", justify="center")
    table.add_column("progress\ncomments", justify="right")
    table.add_column("PR")
    # Issue #52: 重実験フラグ
    table.add_column("weight", justify="center")

    for info in infos:
        staleness = determine_staleness(info.last_commit_age, stale_minutes)
        stale_mark = _STALE_MARK[staleness]

        uncommitted_str = str(info.uncommitted_count)
        if info.uncommitted_count >= 5:
            uncommitted_str = f"{_UNCOMMITTED_MARK}{info.uncommitted_count}"

        path_short = _shorten_path(info.path)
        age_str = _format_age(info.last_commit_age)
        plan_str = "✅" if info.plan_comment_exists else "—"
        pr_str = f"#{info.pr_number} [{info.pr_state}]" if info.pr_number else "—"
        if info.weight == "heavy":
            weight_str = "⚠ heavy"
        elif info.weight == "light":
            weight_str = "light"
        else:
            weight_str = "—"

        table.add_row(
            f"{stale_mark}{path_short}",
            info.branch,
            str(info.commits_ahead),
            uncommitted_str,
            f"{stale_mark}{age_str}",
            plan_str,
            str(info.progress_comment_count),
            pr_str,
            weight_str,
        )

    return table


def build_issues_table(issues: list[IssueInfo], worktrees: list[WorktreeInfo]) -> Table:
    """IssueInfo リストから rich Table を組み立てる（テーブル B）."""
    # worktree path と Issue 番号の対応マップを作成
    wt_map: dict[int, str] = {}
    for wt in worktrees:
        parts = wt.branch.replace("feature/", "").replace("feature-", "")
        try:
            issue_num = int(parts.split("-")[0])
            wt_map[issue_num] = _shorten_path(wt.path)
        except (ValueError, IndexError):
            pass

    table = Table(title="Open Issues", show_lines=True, expand=False)
    table.add_column("#", justify="right", style="bold")
    table.add_column("title", max_width=40)
    table.add_column("state", justify="center")
    table.add_column("blocked_by")
    table.add_column("worktree")

    for issue in issues:
        title_truncated = issue.title[:40] if len(issue.title) > 40 else issue.title
        blocked_str = ", ".join(f"#{n}" for n in issue.blocked_by) if issue.blocked_by else "—"
        assigned = wt_map.get(issue.number, "—")
        table.add_row(
            str(issue.number),
            title_truncated,
            issue.state,
            blocked_str,
            assigned,
        )

    return table


def build_prs_table(prs: list[PRInfo]) -> Table:
    """PRInfo リストから rich Table を組み立てる（テーブル C）."""
    table = Table(title="Recently Merged PRs", show_lines=True, expand=False)
    table.add_column("#", justify="right", style="bold")
    table.add_column("title", max_width=50)
    table.add_column("merged_at")

    for pr in prs:
        table.add_row(str(pr.number), pr.title, pr.merged_at)

    return table


# ---------------------------------------------------------------------------
# JSON 出力
# ---------------------------------------------------------------------------


def _timedelta_to_str(td: timedelta) -> str:
    """Timedelta を秒数文字列に変換する（JSON シリアライズ用）."""
    return str(int(td.total_seconds()))


def to_json_dict(
    worktrees: list[WorktreeInfo],
    issues: list[IssueInfo],
    prs: list[PRInfo],
) -> dict[str, object]:
    """3 つのリストを JSON シリアライズ可能な dict に変換する."""
    wt_dicts: list[dict[str, object]] = []
    for wt in worktrees:
        d = asdict(wt)
        d["last_commit_age"] = _timedelta_to_str(wt.last_commit_age)
        wt_dicts.append(d)

    return {
        "worktrees": wt_dicts,
        "issues": [asdict(i) for i in issues],
        "prs": [asdict(p) for p in prs],
    }


# ---------------------------------------------------------------------------
# メイン
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    """PM status ダッシュボードのエントリポイント."""
    parser = argparse.ArgumentParser(
        description="PM status dashboard — 並列 Agent の進捗を 1 画面で確認する"
    )
    parser.add_argument("--phase", type=int, default=None, help="対象 Phase 番号でフィルタ")
    parser.add_argument(
        "--stale-minutes", type=int, default=10, help="stale 判定の閾値（分、既定 10）"
    )
    parser.add_argument("--no-prs", action="store_true", help="最近 merged PRs 表をスキップ")
    parser.add_argument("--json", action="store_true", dest="json_output", help="JSON 形式で出力")
    args = parser.parse_args(argv)

    # 並列データ収集
    prs: list[PRInfo] = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        wt_future = executor.submit(collect_worktree_info)
        issue_future = executor.submit(collect_open_issues, phase=args.phase)
        pr_future = None if args.no_prs else executor.submit(collect_recent_merged_prs, 10)

        worktrees = wt_future.result()
        issues = issue_future.result()
        if pr_future is not None:
            prs = pr_future.result()

    if args.json_output:
        print(json.dumps(to_json_dict(worktrees, issues, prs), ensure_ascii=False, indent=2))
        return

    console = Console()

    # テーブル A: Active worktrees
    wt_table = build_worktree_table(worktrees, stale_minutes=args.stale_minutes)
    console.print(wt_table)

    # テーブル B: Open Issues
    issue_table = build_issues_table(issues, worktrees)
    console.print(issue_table)

    # テーブル C: Recently merged PRs
    if not args.no_prs:
        pr_table = build_prs_table(prs)
        console.print(pr_table)


if __name__ == "__main__":
    main()
