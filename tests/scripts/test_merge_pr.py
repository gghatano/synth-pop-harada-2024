"""Tests for scripts/merge_pr.py — merge-pr helper script.

このテストファイルは TDD の原則に従い、実装前に書かれている。
各テストケースは scripts/merge_pr.py の振る舞いを規定する。
"""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch


def _get_scripts_path() -> Path:
    """Locate the scripts directory relative to pyproject.toml."""
    here = Path(__file__)
    for parent in here.parents:
        if (parent / "pyproject.toml").exists():
            return parent / "scripts"
    raise FileNotFoundError("pyproject.toml not found in any ancestor directory")


def _import_merge_pr() -> types.ModuleType:
    """Dynamically import merge_pr from scripts/ directory."""
    scripts_path = _get_scripts_path()
    merge_pr_path = scripts_path / "merge_pr.py"
    module_spec = importlib.util.spec_from_file_location("merge_pr", merge_pr_path)
    assert module_spec is not None
    assert module_spec.loader is not None
    module = importlib.util.module_from_spec(module_spec)
    sys.modules["merge_pr"] = module
    module_spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


# ---------------------------------------------------------------------------
# Cycle 1: 正常系 — PR open + CI green → 7 ステップ順次実行
# ---------------------------------------------------------------------------


class TestMergePrNormalFlow:
    """PR open + CI green のとき、7 ステップが順序通り実行される。"""

    def _make_pr_view_response(
        self,
        state: str = "OPEN",
        mergeable: str = "MERGEABLE",
        ci_status: str = "SUCCESS",
        head_ref: str = "feature/48-merge-pr-helper",
    ) -> str:
        """gh pr view の JSON レスポンスを生成するヘルパー。"""
        return json.dumps(
            {
                "state": state,
                "mergeable": mergeable,
                "headRefName": head_ref,
                "statusCheckRollup": [
                    {"state": ci_status, "context": "ci/test"},
                ],
            }
        )

    def test_normal_flow_calls_all_steps_in_order(self) -> None:
        """正常系: 7 ステップが正しい順序で実行される。"""
        m = _import_merge_pr()

        pr_view_response = self._make_pr_view_response()
        run_mock = MagicMock()

        def side_effect(args: list[str], **kwargs: object) -> MagicMock:
            result = MagicMock()
            result.returncode = 0
            result.stdout = ""
            # gh pr view の呼び出しには JSON を返す
            if "pr" in args and "view" in args:
                result.stdout = pr_view_response
            return result

        run_mock.side_effect = side_effect

        with patch.object(m, "_run_cmd", run_mock):
            exit_code = m.merge_pr(pr_number=48, dry_run=False, repo_root="/repo")

        assert exit_code == 0

        # 呼び出し引数リストを確認
        call_args_list = [c[0][0] for c in run_mock.call_args_list]

        # ステップ 1: PR 状態確認
        assert any("pr" in args and "view" in args for args in call_args_list)
        # ステップ 2: gh pr ready
        assert any("pr" in args and "ready" in args for args in call_args_list)
        # ステップ 3: gh pr merge
        assert any(
            "pr" in args and "merge" in args and "--squash" in args for args in call_args_list
        )
        # ステップ 6: git worktree remove
        assert any("worktree" in args and "remove" in args for args in call_args_list)
        # ステップ 7: git branch -D
        assert any("branch" in args and "-D" in args for args in call_args_list)
        # ステップ 8: git checkout develop
        assert any("checkout" in args and "develop" in args for args in call_args_list)
        # ステップ 8: git pull --ff-only
        assert any("pull" in args and "--ff-only" in args for args in call_args_list)

    def test_normal_flow_exit_code_zero(self) -> None:
        """正常系: exit code が 0 であること。"""
        m = _import_merge_pr()

        pr_view_response = self._make_pr_view_response()

        def side_effect(args: list[str], **kwargs: object) -> MagicMock:
            result = MagicMock()
            result.returncode = 0
            result.stdout = pr_view_response if ("pr" in args and "view" in args) else ""
            return result

        with patch.object(m, "_run_cmd", MagicMock(side_effect=side_effect)):
            exit_code = m.merge_pr(pr_number=48, dry_run=False, repo_root="/repo")

        assert exit_code == 0

    def test_normal_flow_worktree_path_derived_from_branch(self) -> None:
        """branch 名から worktree path が正しく導出される。

        feature/48-merge-pr-helper → gitworktree/feature-48-merge-pr-helper
        """
        m = _import_merge_pr()

        pr_view_response = self._make_pr_view_response(head_ref="feature/48-merge-pr-helper")

        captured_worktree_remove_args: list[list[str]] = []

        def side_effect(args: list[str], **kwargs: object) -> MagicMock:
            result = MagicMock()
            result.returncode = 0
            result.stdout = pr_view_response if ("pr" in args and "view" in args) else ""
            if "worktree" in args and "remove" in args:
                captured_worktree_remove_args.append(args)
            return result

        with patch.object(m, "_run_cmd", MagicMock(side_effect=side_effect)):
            m.merge_pr(pr_number=48, dry_run=False, repo_root="/repo")

        assert len(captured_worktree_remove_args) == 1
        remove_args = captured_worktree_remove_args[0]
        # worktree path が feature/N-keyword → gitworktree/feature-N-keyword に変換されている
        assert any("gitworktree/feature-48-merge-pr-helper" in arg for arg in remove_args)


# ---------------------------------------------------------------------------
# Cycle 2: CI fail 系 — statusCheckRollup が FAILURE → exit 1
# ---------------------------------------------------------------------------


class TestMergePrCIFail:
    """CI が失敗している場合、早期 exit 1 で merge しない。"""

    def test_ci_failure_returns_exit_1(self) -> None:
        """CI が FAILURE なら exit 1 を返す。"""
        m = _import_merge_pr()

        pr_view_response = json.dumps(
            {
                "state": "OPEN",
                "mergeable": "MERGEABLE",
                "headRefName": "feature/48-merge-pr-helper",
                "statusCheckRollup": [
                    {"state": "FAILURE", "context": "ci/test"},
                ],
            }
        )

        def side_effect(args: list[str], **kwargs: object) -> MagicMock:
            result = MagicMock()
            result.returncode = 0
            result.stdout = pr_view_response if ("pr" in args and "view" in args) else ""
            return result

        run_mock = MagicMock(side_effect=side_effect)
        with patch.object(m, "_run_cmd", run_mock):
            exit_code = m.merge_pr(pr_number=48, dry_run=False, repo_root="/repo")

        assert exit_code == 1

    def test_ci_failure_does_not_call_merge(self) -> None:
        """CI が FAILURE なら gh pr merge は呼ばれない。"""
        m = _import_merge_pr()

        pr_view_response = json.dumps(
            {
                "state": "OPEN",
                "mergeable": "MERGEABLE",
                "headRefName": "feature/48-merge-pr-helper",
                "statusCheckRollup": [
                    {"state": "FAILURE", "context": "ci/test"},
                ],
            }
        )

        def side_effect(args: list[str], **kwargs: object) -> MagicMock:
            result = MagicMock()
            result.returncode = 0
            result.stdout = pr_view_response if ("pr" in args and "view" in args) else ""
            return result

        run_mock = MagicMock(side_effect=side_effect)
        with patch.object(m, "_run_cmd", run_mock):
            m.merge_pr(pr_number=48, dry_run=False, repo_root="/repo")

        call_args_list = [c[0][0] for c in run_mock.call_args_list]
        # gh pr merge は呼ばれていないこと
        assert not any("pr" in args and "merge" in args for args in call_args_list)

    def test_pending_ci_returns_exit_1(self) -> None:
        """CI が PENDING なら exit 1 を返す（SUCCESS 以外はすべて拒否）。"""
        m = _import_merge_pr()

        pr_view_response = json.dumps(
            {
                "state": "OPEN",
                "mergeable": "MERGEABLE",
                "headRefName": "feature/48-merge-pr-helper",
                "statusCheckRollup": [
                    {"state": "PENDING", "context": "ci/test"},
                ],
            }
        )

        def side_effect(args: list[str], **kwargs: object) -> MagicMock:
            result = MagicMock()
            result.returncode = 0
            result.stdout = pr_view_response if ("pr" in args and "view" in args) else ""
            return result

        with patch.object(m, "_run_cmd", MagicMock(side_effect=side_effect)):
            exit_code = m.merge_pr(pr_number=48, dry_run=False, repo_root="/repo")

        assert exit_code == 1

    def test_empty_status_check_rollup_allows_merge(self) -> None:
        """statusCheckRollup が空の場合（CI なし）は merge を許可する。"""
        m = _import_merge_pr()

        pr_view_response = json.dumps(
            {
                "state": "OPEN",
                "mergeable": "MERGEABLE",
                "headRefName": "feature/48-merge-pr-helper",
                "statusCheckRollup": [],
            }
        )

        def side_effect(args: list[str], **kwargs: object) -> MagicMock:
            result = MagicMock()
            result.returncode = 0
            result.stdout = pr_view_response if ("pr" in args and "view" in args) else ""
            return result

        with patch.object(m, "_run_cmd", MagicMock(side_effect=side_effect)):
            exit_code = m.merge_pr(pr_number=48, dry_run=False, repo_root="/repo")

        assert exit_code == 0


# ---------------------------------------------------------------------------
# Cycle 3: 既 merged 系 — state == MERGED → no-op + warning
# ---------------------------------------------------------------------------


class TestMergePrAlreadyMerged:
    """PR が既に merged の場合、merge を試みずに警告を出して exit 0。"""

    def test_already_merged_returns_exit_0(self) -> None:
        """既 merged PR は no-op で exit 0 を返す。"""
        m = _import_merge_pr()

        pr_view_response = json.dumps(
            {
                "state": "MERGED",
                "mergeable": "UNKNOWN",
                "headRefName": "feature/48-merge-pr-helper",
                "statusCheckRollup": [],
            }
        )

        def side_effect(args: list[str], **kwargs: object) -> MagicMock:
            result = MagicMock()
            result.returncode = 0
            result.stdout = pr_view_response if ("pr" in args and "view" in args) else ""
            return result

        with patch.object(m, "_run_cmd", MagicMock(side_effect=side_effect)):
            exit_code = m.merge_pr(pr_number=48, dry_run=False, repo_root="/repo")

        assert exit_code == 0

    def test_already_merged_does_not_call_gh_pr_merge(self) -> None:
        """既 merged PR は gh pr merge を呼ばない。"""
        m = _import_merge_pr()

        pr_view_response = json.dumps(
            {
                "state": "MERGED",
                "mergeable": "UNKNOWN",
                "headRefName": "feature/48-merge-pr-helper",
                "statusCheckRollup": [],
            }
        )

        def side_effect(args: list[str], **kwargs: object) -> MagicMock:
            result = MagicMock()
            result.returncode = 0
            result.stdout = pr_view_response if ("pr" in args and "view" in args) else ""
            return result

        run_mock = MagicMock(side_effect=side_effect)
        with patch.object(m, "_run_cmd", run_mock):
            m.merge_pr(pr_number=48, dry_run=False, repo_root="/repo")

        call_args_list = [c[0][0] for c in run_mock.call_args_list]
        assert not any("pr" in args and "merge" in args for args in call_args_list)

    def test_closed_pr_returns_exit_1(self) -> None:
        """CLOSED（close された PR）は exit 1 を返す。"""
        m = _import_merge_pr()

        pr_view_response = json.dumps(
            {
                "state": "CLOSED",
                "mergeable": "UNKNOWN",
                "headRefName": "feature/48-merge-pr-helper",
                "statusCheckRollup": [],
            }
        )

        def side_effect(args: list[str], **kwargs: object) -> MagicMock:
            result = MagicMock()
            result.returncode = 0
            result.stdout = pr_view_response if ("pr" in args and "view" in args) else ""
            return result

        with patch.object(m, "_run_cmd", MagicMock(side_effect=side_effect)):
            exit_code = m.merge_pr(pr_number=48, dry_run=False, repo_root="/repo")

        assert exit_code == 1


# ---------------------------------------------------------------------------
# Cycle 4: worktree 不在系 — worktree remove 失敗 → warning で続行
# ---------------------------------------------------------------------------


class TestMergePrWorktreeAbsent:
    """worktree が存在しない場合、警告を出して branch -D まで続行する。"""

    def test_worktree_remove_failure_continues_to_branch_delete(self) -> None:
        """worktree remove が失敗しても、branch -D が呼ばれる。"""
        m = _import_merge_pr()

        pr_view_response = json.dumps(
            {
                "state": "OPEN",
                "mergeable": "MERGEABLE",
                "headRefName": "feature/48-merge-pr-helper",
                "statusCheckRollup": [{"state": "SUCCESS", "context": "ci/test"}],
            }
        )

        def side_effect(args: list[str], **kwargs: object) -> MagicMock:
            result = MagicMock()
            result.returncode = 0
            result.stdout = pr_view_response if ("pr" in args and "view" in args) else ""
            # worktree remove は失敗させる
            if "worktree" in args and "remove" in args:
                result.returncode = 1
                result.stderr = "error: worktree not found"
            return result

        run_mock = MagicMock(side_effect=side_effect)
        with patch.object(m, "_run_cmd", run_mock):
            exit_code = m.merge_pr(pr_number=48, dry_run=False, repo_root="/repo")

        # exit code は 0（worktree 不在は warning のみ）
        assert exit_code == 0

        call_args_list = [c[0][0] for c in run_mock.call_args_list]
        # branch -D は呼ばれる
        assert any("branch" in args and "-D" in args for args in call_args_list)
        # git pull --ff-only も呼ばれる
        assert any("pull" in args and "--ff-only" in args for args in call_args_list)

    def test_branch_delete_failure_continues_to_pull(self) -> None:
        """branch -D が失敗しても、git pull --ff-only が呼ばれる。"""
        m = _import_merge_pr()

        pr_view_response = json.dumps(
            {
                "state": "OPEN",
                "mergeable": "MERGEABLE",
                "headRefName": "feature/48-merge-pr-helper",
                "statusCheckRollup": [{"state": "SUCCESS", "context": "ci/test"}],
            }
        )

        def side_effect(args: list[str], **kwargs: object) -> MagicMock:
            result = MagicMock()
            result.returncode = 0
            result.stdout = pr_view_response if ("pr" in args and "view" in args) else ""
            # branch -D は失敗させる
            if "branch" in args and "-D" in args:
                result.returncode = 1
                result.stderr = "error: branch not found"
            return result

        run_mock = MagicMock(side_effect=side_effect)
        with patch.object(m, "_run_cmd", run_mock):
            exit_code = m.merge_pr(pr_number=48, dry_run=False, repo_root="/repo")

        assert exit_code == 0

        call_args_list = [c[0][0] for c in run_mock.call_args_list]
        assert any("pull" in args and "--ff-only" in args for args in call_args_list)


# ---------------------------------------------------------------------------
# Cycle 5: dry-run 系 — コマンドを実行せず echo のみ
# ---------------------------------------------------------------------------


class TestMergePrDryRun:
    """--dry-run フラグ時はコマンドを実行せず、手順を表示して exit 0。"""

    def test_dry_run_does_not_call_gh_pr_merge(self) -> None:
        """dry-run 時は gh pr merge が呼ばれない。"""
        m = _import_merge_pr()

        pr_view_response = json.dumps(
            {
                "state": "OPEN",
                "mergeable": "MERGEABLE",
                "headRefName": "feature/48-merge-pr-helper",
                "statusCheckRollup": [{"state": "SUCCESS", "context": "ci/test"}],
            }
        )

        def side_effect(args: list[str], **kwargs: object) -> MagicMock:
            result = MagicMock()
            result.returncode = 0
            result.stdout = pr_view_response if ("pr" in args and "view" in args) else ""
            return result

        run_mock = MagicMock(side_effect=side_effect)
        with patch.object(m, "_run_cmd", run_mock):
            exit_code = m.merge_pr(pr_number=48, dry_run=True, repo_root="/repo")

        assert exit_code == 0

        call_args_list = [c[0][0] for c in run_mock.call_args_list]
        # dry-run 時は gh pr merge を呼ばない
        assert not any("pr" in args and "merge" in args for args in call_args_list)

    def test_dry_run_does_not_call_git_worktree_remove(self) -> None:
        """dry-run 時は git worktree remove が呼ばれない。"""
        m = _import_merge_pr()

        pr_view_response = json.dumps(
            {
                "state": "OPEN",
                "mergeable": "MERGEABLE",
                "headRefName": "feature/48-merge-pr-helper",
                "statusCheckRollup": [{"state": "SUCCESS", "context": "ci/test"}],
            }
        )

        def side_effect(args: list[str], **kwargs: object) -> MagicMock:
            result = MagicMock()
            result.returncode = 0
            result.stdout = pr_view_response if ("pr" in args and "view" in args) else ""
            return result

        run_mock = MagicMock(side_effect=side_effect)
        with patch.object(m, "_run_cmd", run_mock):
            m.merge_pr(pr_number=48, dry_run=True, repo_root="/repo")

        call_args_list = [c[0][0] for c in run_mock.call_args_list]
        assert not any("worktree" in args and "remove" in args for args in call_args_list)

    def test_dry_run_returns_exit_0(self) -> None:
        """dry-run は必ず exit 0。"""
        m = _import_merge_pr()

        pr_view_response = json.dumps(
            {
                "state": "OPEN",
                "mergeable": "MERGEABLE",
                "headRefName": "feature/48-merge-pr-helper",
                "statusCheckRollup": [{"state": "SUCCESS", "context": "ci/test"}],
            }
        )

        def side_effect(args: list[str], **kwargs: object) -> MagicMock:
            result = MagicMock()
            result.returncode = 0
            result.stdout = pr_view_response if ("pr" in args and "view" in args) else ""
            return result

        with patch.object(m, "_run_cmd", MagicMock(side_effect=side_effect)):
            exit_code = m.merge_pr(pr_number=48, dry_run=True, repo_root="/repo")

        assert exit_code == 0


# ---------------------------------------------------------------------------
# Cycle 6: branch_to_worktree_path 変換関数
# ---------------------------------------------------------------------------


class TestBranchToWorktreePath:
    """branch 名 → worktree path の変換ロジックを単体で検証。"""

    def test_feature_branch_to_worktree_path(self) -> None:
        """feature/48-merge-pr-helper → gitworktree/feature-48-merge-pr-helper"""
        m = _import_merge_pr()
        result = m.branch_to_worktree_path("feature/48-merge-pr-helper", repo_root="/repo")
        assert result == "/repo/gitworktree/feature-48-merge-pr-helper"

    def test_feature_branch_with_numbers(self) -> None:
        """feature/42-add-sa-core → gitworktree/feature-42-add-sa-core"""
        m = _import_merge_pr()
        result = m.branch_to_worktree_path("feature/42-add-sa-core", repo_root="/repo")
        assert result == "/repo/gitworktree/feature-42-add-sa-core"

    def test_non_feature_branch_returns_none(self) -> None:
        """feature/ で始まらないブランチは None を返す。"""
        m = _import_merge_pr()
        result = m.branch_to_worktree_path("main", repo_root="/repo")
        assert result is None

    def test_develop_branch_returns_none(self) -> None:
        """develop ブランチは None を返す。"""
        m = _import_merge_pr()
        result = m.branch_to_worktree_path("develop", repo_root="/repo")
        assert result is None


# ---------------------------------------------------------------------------
# Cycle 7: check_pr_status 関数
# ---------------------------------------------------------------------------


class TestCheckPRStatus:
    """check_pr_status が PR の状態を正しく解析する。"""

    def test_open_ci_success_returns_ok(self) -> None:
        """OPEN + CI SUCCESS → ('ok', state, head_ref)"""
        m = _import_merge_pr()

        pr_data = {
            "state": "OPEN",
            "mergeable": "MERGEABLE",
            "headRefName": "feature/48-merge-pr-helper",
            "statusCheckRollup": [{"state": "SUCCESS", "context": "ci/test"}],
        }

        status, state, head_ref = m.check_pr_status(pr_data)
        assert status == "ok"
        assert state == "OPEN"
        assert head_ref == "feature/48-merge-pr-helper"

    def test_merged_returns_already_merged(self) -> None:
        """MERGED → ('already_merged', state, head_ref)"""
        m = _import_merge_pr()

        pr_data = {
            "state": "MERGED",
            "mergeable": "UNKNOWN",
            "headRefName": "feature/48-merge-pr-helper",
            "statusCheckRollup": [],
        }

        status, state, _head_ref = m.check_pr_status(pr_data)
        assert status == "already_merged"
        assert state == "MERGED"

    def test_closed_returns_error(self) -> None:
        """CLOSED → ('error', state, head_ref)"""
        m = _import_merge_pr()

        pr_data = {
            "state": "CLOSED",
            "mergeable": "UNKNOWN",
            "headRefName": "feature/48-merge-pr-helper",
            "statusCheckRollup": [],
        }

        status, _state, _head_ref = m.check_pr_status(pr_data)
        assert status == "error"

    def test_ci_failure_returns_ci_failed(self) -> None:
        """OPEN + CI FAILURE → ('ci_failed', state, head_ref)"""
        m = _import_merge_pr()

        pr_data = {
            "state": "OPEN",
            "mergeable": "MERGEABLE",
            "headRefName": "feature/48-merge-pr-helper",
            "statusCheckRollup": [{"state": "FAILURE", "context": "ci/test"}],
        }

        status, _state, _head_ref = m.check_pr_status(pr_data)
        assert status == "ci_failed"

    def test_multiple_checks_last_one_wins(self) -> None:
        """複数の CI チェックがある場合、最後の state が判定に使われる。"""
        m = _import_merge_pr()

        pr_data = {
            "state": "OPEN",
            "mergeable": "MERGEABLE",
            "headRefName": "feature/48-merge-pr-helper",
            "statusCheckRollup": [
                {"state": "SUCCESS", "context": "ci/lint"},
                {"state": "FAILURE", "context": "ci/test"},
            ],
        }

        status, _state, _head_ref = m.check_pr_status(pr_data)
        assert status == "ci_failed"
