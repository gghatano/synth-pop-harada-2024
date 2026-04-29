"""Tests for scripts/pm_status.py — PM dashboard for parallel Agent monitoring."""

from __future__ import annotations

import json
import types
from datetime import timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _get_scripts_path() -> Path:
    """Locate the scripts directory relative to pyproject.toml."""
    here = Path(__file__)
    for parent in here.parents:
        if (parent / "pyproject.toml").exists():
            return parent / "scripts"
    raise FileNotFoundError("pyproject.toml not found in any ancestor directory")


# ---------------------------------------------------------------------------
# Helpers: dynamically import pm_status from scripts/
# ---------------------------------------------------------------------------


def _import_pm_status() -> types.ModuleType:
    import importlib.util
    import sys

    scripts_path = _get_scripts_path()
    pm_path = scripts_path / "pm_status.py"
    module_spec = importlib.util.spec_from_file_location("pm_status", pm_path)
    assert module_spec is not None
    assert module_spec.loader is not None
    module = importlib.util.module_from_spec(module_spec)
    # dataclass requires the module to be in sys.modules so __module__ lookup works
    sys.modules["pm_status"] = module
    module_spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


# ---------------------------------------------------------------------------
# Cycle 1: WorktreeInfo dataclass and collect_worktree_info
# ---------------------------------------------------------------------------


class TestWorktreeInfoDataclass:
    """WorktreeInfo dataclass should hold all worktree metadata."""

    def test_worktree_info_has_required_fields(self) -> None:
        pm = _import_pm_status()
        info = pm.WorktreeInfo(
            path="/tmp/worktree",
            branch="feature/40-pm-dashboard",
            commits_ahead=3,
            uncommitted_count=1,
            last_commit_age=timedelta(minutes=5),
            plan_comment_exists=True,
            progress_comment_count=2,
            pr_number=42,
            pr_state="DRAFT",
        )
        assert info.path == "/tmp/worktree"
        assert info.branch == "feature/40-pm-dashboard"
        assert info.commits_ahead == 3
        assert info.uncommitted_count == 1
        assert info.last_commit_age == timedelta(minutes=5)
        assert info.plan_comment_exists is True
        assert info.progress_comment_count == 2
        assert info.pr_number == 42
        assert info.pr_state == "DRAFT"

    def test_worktree_info_pr_fields_optional(self) -> None:
        pm = _import_pm_status()
        info = pm.WorktreeInfo(
            path="/tmp/worktree",
            branch="feature/40-pm-dashboard",
            commits_ahead=0,
            uncommitted_count=0,
            last_commit_age=timedelta(minutes=0),
            plan_comment_exists=False,
            progress_comment_count=0,
            pr_number=None,
            pr_state=None,
        )
        assert info.pr_number is None
        assert info.pr_state is None

    def test_worktree_info_weight_default_none(self) -> None:
        """weight field は省略時 None（Issue #52、後方互換）."""
        pm = _import_pm_status()
        info = pm.WorktreeInfo(
            path="/tmp/worktree",
            branch="feature/x",
            commits_ahead=0,
            uncommitted_count=0,
            last_commit_age=timedelta(minutes=0),
            plan_comment_exists=False,
            progress_comment_count=0,
            pr_number=None,
            pr_state=None,
        )
        assert info.weight is None

    def test_worktree_info_weight_heavy(self) -> None:
        """weight='heavy' を保持する."""
        pm = _import_pm_status()
        info = pm.WorktreeInfo(
            path="/tmp/worktree",
            branch="feature/x",
            commits_ahead=0,
            uncommitted_count=0,
            last_commit_age=timedelta(minutes=0),
            plan_comment_exists=False,
            progress_comment_count=0,
            pr_number=None,
            pr_state=None,
            weight="heavy",
        )
        assert info.weight == "heavy"


class TestCollectWorktreeInfo:
    """collect_worktree_info should parse git output into WorktreeInfo."""

    def test_collect_worktree_info_basic(self) -> None:
        pm = _import_pm_status()

        def mock_run(args: list[str], cwd: str | None = None) -> str:
            cmd = " ".join(args)
            if "worktree list" in cmd:
                return (
                    "/repo/main  abc1234  [main]\n"
                    "/repo/gitworktree/feature-40  def5678  [feature/40-pm-dashboard]\n"
                )
            if "rev-list" in cmd and "origin/develop" in cmd:
                return "3\n"
            if "status --porcelain" in cmd:
                return "M  file1.py\n?? file2.py\n"
            if "log -1 --format=%ct" in cmd:
                # Return unix timestamp from 5 minutes ago
                import time

                return str(int(time.time()) - 300)
            return ""

        with (
            patch.object(pm, "_run_cmd", side_effect=mock_run),
            patch.object(pm, "_get_issue_comment_counts", return_value=(True, 2)),
            patch.object(pm, "_get_pr_for_branch", return_value=(42, "DRAFT")),
        ):
            infos = pm.collect_worktree_info()

        # Should only include feature worktrees (not main)
        assert len(infos) == 1
        info = infos[0]
        assert "feature-40" in info.path
        assert info.branch == "feature/40-pm-dashboard"
        assert info.commits_ahead == 3
        assert info.uncommitted_count == 2
        assert abs(info.last_commit_age.total_seconds() - 300) < 10
        assert info.plan_comment_exists is True
        assert info.progress_comment_count == 2
        assert info.pr_number == 42
        assert info.pr_state == "DRAFT"

    def test_collect_worktree_info_excludes_main_branch(self) -> None:
        pm = _import_pm_status()

        def mock_run(args: list[str], cwd: str | None = None) -> str:
            cmd = " ".join(args)
            if "worktree list" in cmd:
                return "/repo  abc1234  [main]\n/repo2  abc1234  [develop]\n"
            return ""

        with patch.object(pm, "_run_cmd", side_effect=mock_run):
            infos = pm.collect_worktree_info()

        assert len(infos) == 0

    def test_collect_worktree_info_handles_git_error(self) -> None:
        pm = _import_pm_status()

        def mock_run(args: list[str], cwd: str | None = None) -> str:
            raise RuntimeError("git command failed")

        with patch.object(pm, "_run_cmd", side_effect=mock_run):
            # Should not raise, should return empty list
            infos = pm.collect_worktree_info()

        assert infos == []


# ---------------------------------------------------------------------------
# Cycle 2: IssueInfo dataclass and collect_open_issues
# ---------------------------------------------------------------------------


class TestIssueInfoDataclass:
    """IssueInfo dataclass should hold Issue metadata."""

    def test_issue_info_has_required_fields(self) -> None:
        pm = _import_pm_status()
        info = pm.IssueInfo(
            number=40,
            title="PM can monitor agents",
            state="OPEN",
            blocked_by=[38, 39],
            assigned_worktree="/repo/gitworktree/feature-40",
        )
        assert info.number == 40
        assert info.title == "PM can monitor agents"
        assert info.state == "OPEN"
        assert info.blocked_by == [38, 39]
        assert info.assigned_worktree == "/repo/gitworktree/feature-40"

    def test_issue_info_optional_fields(self) -> None:
        pm = _import_pm_status()
        info = pm.IssueInfo(
            number=40,
            title="title",
            state="OPEN",
            blocked_by=[],
            assigned_worktree=None,
        )
        assert info.blocked_by == []
        assert info.assigned_worktree is None


class TestCollectOpenIssues:
    """collect_open_issues should parse gh CLI output into IssueInfo list."""

    def test_collect_open_issues_with_phase_filter(self) -> None:
        pm = _import_pm_status()

        gh_output = json.dumps(
            [
                {
                    "number": 40,
                    "title": "[phase-2] PM dashboard",
                    "state": "OPEN",
                    "labels": [{"name": "phase-2"}],
                    "body": "## blocked_by\n- #38\n",
                },
                {
                    "number": 39,
                    "title": "[phase-2] another issue",
                    "state": "OPEN",
                    "labels": [{"name": "phase-2"}],
                    "body": "",
                },
            ]
        )

        def mock_run(args: list[str], cwd: str | None = None) -> str:
            if "issue list" in " ".join(args):
                return gh_output
            return ""

        with patch.object(pm, "_run_cmd", side_effect=mock_run):
            issues = pm.collect_open_issues(phase=2)

        assert len(issues) == 2
        assert issues[0].number == 40
        assert issues[0].title == "[phase-2] PM dashboard"

    def test_collect_open_issues_handles_gh_error(self) -> None:
        pm = _import_pm_status()

        def mock_run(args: list[str], cwd: str | None = None) -> str:
            raise RuntimeError("gh command failed")

        with patch.object(pm, "_run_cmd", side_effect=mock_run):
            issues = pm.collect_open_issues(phase=None)

        assert issues == []

    def test_collect_open_issues_no_phase_returns_all(self) -> None:
        pm = _import_pm_status()

        gh_output = json.dumps(
            [
                {
                    "number": 10,
                    "title": "some issue",
                    "state": "OPEN",
                    "labels": [{"name": "phase-1"}],
                    "body": "",
                },
            ]
        )

        def mock_run(args: list[str], cwd: str | None = None) -> str:
            if "issue list" in " ".join(args):
                return gh_output
            return ""

        with patch.object(pm, "_run_cmd", side_effect=mock_run):
            issues = pm.collect_open_issues(phase=None)

        assert len(issues) == 1


# ---------------------------------------------------------------------------
# Cycle 3: PRInfo dataclass and collect_recent_merged_prs
# ---------------------------------------------------------------------------


class TestPRInfoDataclass:
    """PRInfo dataclass should hold PR metadata."""

    def test_pr_info_has_required_fields(self) -> None:
        pm = _import_pm_status()
        info = pm.PRInfo(number=10, title="feat: add something", merged_at="2024-01-01T00:00:00Z")
        assert info.number == 10
        assert info.title == "feat: add something"
        assert info.merged_at == "2024-01-01T00:00:00Z"


class TestCollectRecentMergedPRs:
    """collect_recent_merged_prs should parse gh CLI output into PRInfo list."""

    def test_collect_recent_merged_prs_returns_list(self) -> None:
        pm = _import_pm_status()

        gh_output = json.dumps(
            [
                {"number": 5, "title": "feat: something", "mergedAt": "2024-01-01T10:00:00Z"},
                {"number": 4, "title": "fix: bug", "mergedAt": "2024-01-01T09:00:00Z"},
            ]
        )

        def mock_run(args: list[str], cwd: str | None = None) -> str:
            if "pr list" in " ".join(args):
                return gh_output
            return ""

        with patch.object(pm, "_run_cmd", side_effect=mock_run):
            prs = pm.collect_recent_merged_prs(limit=10)

        assert len(prs) == 2
        assert prs[0].number == 5
        assert prs[0].title == "feat: something"
        assert prs[0].merged_at == "2024-01-01T10:00:00Z"

    def test_collect_recent_merged_prs_handles_error(self) -> None:
        pm = _import_pm_status()

        def mock_run(args: list[str], cwd: str | None = None) -> str:
            raise RuntimeError("gh failed")

        with patch.object(pm, "_run_cmd", side_effect=mock_run):
            prs = pm.collect_recent_merged_prs(limit=10)

        assert prs == []

    def test_collect_recent_merged_prs_respects_limit(self) -> None:
        pm = _import_pm_status()

        gh_output = json.dumps(
            [
                {"number": i, "title": f"pr {i}", "mergedAt": "2024-01-01T00:00:00Z"}
                for i in range(10)
            ]
        )

        def mock_run(args: list[str], cwd: str | None = None) -> str:
            if "pr list" in " ".join(args):
                # Verify limit argument is passed
                assert "--limit" in args or "-L" in args
                return gh_output
            return ""

        with patch.object(pm, "_run_cmd", side_effect=mock_run):
            prs = pm.collect_recent_merged_prs(limit=10)

        assert len(prs) == 10


# ---------------------------------------------------------------------------
# Cycle 4: determine_staleness pure function
# ---------------------------------------------------------------------------


class TestDetermineStaleness:
    """determine_staleness should classify last_commit_age against stale_minutes threshold."""

    def test_fresh_returns_ok(self) -> None:
        pm = _import_pm_status()
        result = pm.determine_staleness(timedelta(minutes=5), stale_minutes=10)
        assert result == "ok"

    def test_exactly_at_threshold_returns_warn(self) -> None:
        pm = _import_pm_status()
        result = pm.determine_staleness(timedelta(minutes=10), stale_minutes=10)
        assert result == "warn"

    def test_between_threshold_and_double_returns_warn(self) -> None:
        pm = _import_pm_status()
        result = pm.determine_staleness(timedelta(minutes=15), stale_minutes=10)
        assert result == "warn"

    def test_at_double_threshold_returns_danger(self) -> None:
        pm = _import_pm_status()
        result = pm.determine_staleness(timedelta(minutes=20), stale_minutes=10)
        assert result == "danger"

    def test_beyond_double_threshold_returns_danger(self) -> None:
        pm = _import_pm_status()
        result = pm.determine_staleness(timedelta(minutes=30), stale_minutes=10)
        assert result == "danger"

    def test_custom_stale_minutes(self) -> None:
        pm = _import_pm_status()
        assert pm.determine_staleness(timedelta(minutes=3), stale_minutes=5) == "ok"
        assert pm.determine_staleness(timedelta(minutes=5), stale_minutes=5) == "warn"
        assert pm.determine_staleness(timedelta(minutes=10), stale_minutes=5) == "danger"

    def test_zero_age_is_ok(self) -> None:
        pm = _import_pm_status()
        result = pm.determine_staleness(timedelta(seconds=0), stale_minutes=10)
        assert result == "ok"


# ---------------------------------------------------------------------------
# Cycle 5: build_worktree_table rich Table
# ---------------------------------------------------------------------------


class TestBuildWorktreeTable:
    """build_worktree_table should produce a rich Table with correct columns and rows."""

    def test_table_has_correct_column_count(self) -> None:
        pm = _import_pm_status()
        from rich.table import Table

        infos = [
            pm.WorktreeInfo(
                path="/repo/gitworktree/feature-40-pm-dashboard",
                branch="feature/40-pm-dashboard",
                commits_ahead=2,
                uncommitted_count=0,
                last_commit_age=timedelta(minutes=3),
                plan_comment_exists=True,
                progress_comment_count=1,
                pr_number=10,
                pr_state="DRAFT",
            )
        ]
        table = pm.build_worktree_table(infos, stale_minutes=10)
        assert isinstance(table, Table)
        # 9 列: 既存 8 + Weight (Issue #52)
        assert len(table.columns) == 9

    def test_table_has_correct_row_count(self) -> None:
        pm = _import_pm_status()

        infos = [
            pm.WorktreeInfo(
                path=f"/repo/gitworktree/feature-{i}",
                branch=f"feature/{i}",
                commits_ahead=0,
                uncommitted_count=0,
                last_commit_age=timedelta(minutes=0),
                plan_comment_exists=False,
                progress_comment_count=0,
                pr_number=None,
                pr_state=None,
            )
            for i in range(3)
        ]
        table = pm.build_worktree_table(infos, stale_minutes=10)
        assert table.row_count == 3

    def test_table_stale_warn_marker(self) -> None:
        """A worktree with last_commit_age >= stale_minutes should have 🟡 in path column."""
        pm = _import_pm_status()
        from io import StringIO

        from rich.console import Console

        infos = [
            pm.WorktreeInfo(
                path="/repo/gitworktree/feature-40",
                branch="feature/40",
                commits_ahead=0,
                uncommitted_count=0,
                last_commit_age=timedelta(minutes=15),
                plan_comment_exists=True,
                progress_comment_count=0,
                pr_number=None,
                pr_state=None,
            )
        ]
        table = pm.build_worktree_table(infos, stale_minutes=10)
        buf = StringIO()
        console = Console(file=buf, no_color=True, width=200)
        console.print(table)
        rendered = buf.getvalue()
        assert "🟡" in rendered

    def test_table_danger_marker(self) -> None:
        """A worktree with last_commit_age >= stale_minutes*2 should have 🔴."""
        pm = _import_pm_status()
        from io import StringIO

        from rich.console import Console

        infos = [
            pm.WorktreeInfo(
                path="/repo/gitworktree/feature-40",
                branch="feature/40",
                commits_ahead=0,
                uncommitted_count=0,
                last_commit_age=timedelta(minutes=25),
                plan_comment_exists=True,
                progress_comment_count=0,
                pr_number=None,
                pr_state=None,
            )
        ]
        table = pm.build_worktree_table(infos, stale_minutes=10)
        buf = StringIO()
        console = Console(file=buf, no_color=True, width=200)
        console.print(table)
        rendered = buf.getvalue()
        assert "🔴" in rendered

    def test_table_many_uncommitted_marker(self) -> None:
        """A worktree with uncommitted_count >= 5 should have 🟠."""
        pm = _import_pm_status()
        from io import StringIO

        from rich.console import Console

        infos = [
            pm.WorktreeInfo(
                path="/repo/gitworktree/feature-40",
                branch="feature/40",
                commits_ahead=0,
                uncommitted_count=5,
                last_commit_age=timedelta(minutes=1),
                plan_comment_exists=True,
                progress_comment_count=0,
                pr_number=None,
                pr_state=None,
            )
        ]
        table = pm.build_worktree_table(infos, stale_minutes=10)
        buf = StringIO()
        console = Console(file=buf, no_color=True, width=200)
        console.print(table)
        rendered = buf.getvalue()
        assert "🟠" in rendered

    def test_table_displays_heavy_marker(self) -> None:
        """weight='heavy' の worktree は ⚠ 付きで表示される（Issue #52）."""
        pm = _import_pm_status()
        from io import StringIO

        from rich.console import Console

        infos = [
            pm.WorktreeInfo(
                path="/repo/gitworktree/feature-51",
                branch="feature/51",
                commits_ahead=0,
                uncommitted_count=0,
                last_commit_age=timedelta(minutes=1),
                plan_comment_exists=True,
                progress_comment_count=0,
                pr_number=None,
                pr_state=None,
                weight="heavy",
            )
        ]
        table = pm.build_worktree_table(infos, stale_minutes=10)
        buf = StringIO()
        console = Console(file=buf, no_color=True, width=200)
        console.print(table)
        rendered = buf.getvalue()
        assert "⚠" in rendered
        assert "heavy" in rendered


# ---------------------------------------------------------------------------
# Cycle 6: WEIGHT.md detection (Issue #52)
# ---------------------------------------------------------------------------


class TestDetectWeight:
    """_detect_weight reads experiments/*/WEIGHT.md and returns a weight tier or None."""

    def test_returns_heavy_when_present(self, tmp_path: Path) -> None:
        pm = _import_pm_status()
        exp = tmp_path / "experiments" / "2026-04-29-foo"
        exp.mkdir(parents=True)
        (exp / "WEIGHT.md").write_text("heavy\n")
        assert pm._detect_weight(str(tmp_path)) == "heavy"

    def test_returns_light_when_only_light(self, tmp_path: Path) -> None:
        pm = _import_pm_status()
        exp = tmp_path / "experiments" / "2026-04-29-foo"
        exp.mkdir(parents=True)
        (exp / "WEIGHT.md").write_text("light\n")
        assert pm._detect_weight(str(tmp_path)) == "light"

    def test_returns_none_when_no_weight_files(self, tmp_path: Path) -> None:
        pm = _import_pm_status()
        (tmp_path / "experiments" / "2026-04-29-foo").mkdir(parents=True)
        # no WEIGHT.md
        assert pm._detect_weight(str(tmp_path)) is None

    def test_returns_none_when_no_experiments_dir(self, tmp_path: Path) -> None:
        pm = _import_pm_status()
        # tmp_path に experiments/ すらない
        assert pm._detect_weight(str(tmp_path)) is None

    def test_max_rule_returns_heavy_when_mixed(self, tmp_path: Path) -> None:
        """light + heavy が混在したら heavy を返す（max-rule）."""
        pm = _import_pm_status()
        for name, content in [("exp_l", "light"), ("exp_h", "heavy")]:
            d = tmp_path / "experiments" / name
            d.mkdir(parents=True)
            (d / "WEIGHT.md").write_text(content + "\n")
        assert pm._detect_weight(str(tmp_path)) == "heavy"

    def test_unknown_value_skipped_with_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """light/heavy 以外は warning を出して skip（None を返す）."""
        pm = _import_pm_status()
        exp = tmp_path / "experiments" / "exp_bad"
        exp.mkdir(parents=True)
        (exp / "WEIGHT.md").write_text("MEDIUM\n")
        with caplog.at_level("WARNING"):
            result = pm._detect_weight(str(tmp_path))
        assert result is None
        assert any("MEDIUM" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Cycle 7: main function integration, CLI flags
# ---------------------------------------------------------------------------


class TestMainFunction:
    """main() should accept CLI args and produce output without error."""

    def test_main_with_no_args_runs(self) -> None:
        pm = _import_pm_status()

        with (
            patch.object(pm, "collect_worktree_info", return_value=[]),
            patch.object(pm, "collect_open_issues", return_value=[]),
            patch.object(pm, "collect_recent_merged_prs", return_value=[]),
        ):
            # Should not raise
            pm.main(["--stale-minutes", "10"])

    def test_main_no_prs_flag(self) -> None:
        pm = _import_pm_status()

        collect_prs_mock = MagicMock(return_value=[])
        with (
            patch.object(pm, "collect_worktree_info", return_value=[]),
            patch.object(pm, "collect_open_issues", return_value=[]),
            patch.object(pm, "collect_recent_merged_prs", collect_prs_mock),
        ):
            pm.main(["--no-prs"])
            collect_prs_mock.assert_not_called()

    def test_main_json_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        pm = _import_pm_status()

        wt = pm.WorktreeInfo(
            path="/repo/feature-40",
            branch="feature/40",
            commits_ahead=1,
            uncommitted_count=0,
            last_commit_age=timedelta(minutes=2),
            plan_comment_exists=True,
            progress_comment_count=0,
            pr_number=None,
            pr_state=None,
        )

        with (
            patch.object(pm, "collect_worktree_info", return_value=[wt]),
            patch.object(pm, "collect_open_issues", return_value=[]),
            patch.object(pm, "collect_recent_merged_prs", return_value=[]),
        ):
            pm.main(["--json"])

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "worktrees" in data
        assert "issues" in data
        assert "prs" in data
        assert len(data["worktrees"]) == 1

    def test_main_phase_filter_passed_to_collect_issues(self) -> None:
        pm = _import_pm_status()

        collect_issues_mock = MagicMock(return_value=[])
        with (
            patch.object(pm, "collect_worktree_info", return_value=[]),
            patch.object(pm, "collect_open_issues", collect_issues_mock),
            patch.object(pm, "collect_recent_merged_prs", return_value=[]),
        ):
            pm.main(["--phase", "2"])
            collect_issues_mock.assert_called_once_with(phase=2)

    def test_main_stale_minutes_passed_to_build_table(self) -> None:
        pm = _import_pm_status()

        wt = pm.WorktreeInfo(
            path="/repo/feature-40",
            branch="feature/40",
            commits_ahead=0,
            uncommitted_count=0,
            last_commit_age=timedelta(minutes=0),
            plan_comment_exists=False,
            progress_comment_count=0,
            pr_number=None,
            pr_state=None,
        )

        build_mock = MagicMock(return_value=MagicMock())
        with (
            patch.object(pm, "collect_worktree_info", return_value=[wt]),
            patch.object(pm, "collect_open_issues", return_value=[]),
            patch.object(pm, "collect_recent_merged_prs", return_value=[]),
            patch.object(pm, "build_worktree_table", build_mock),
        ):
            pm.main(["--stale-minutes", "5"])
            build_mock.assert_called_once_with([wt], stale_minutes=5)
