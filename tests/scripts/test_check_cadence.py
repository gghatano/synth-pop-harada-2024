"""tests/scripts/test_check_cadence.py

scripts/check_cadence.py のテスト。
uncommitted ファイル数・行数の閾値チェックと CLI フラグの動作を確認する。

Issue #46: Agent が stall せず commit cadence を守る仕組みの物理的強制
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


def _find_repo_root() -> Path:
    """pyproject.toml を含む最近接の祖先を repo root とみなす."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError(f"pyproject.toml が {here} から辿れない")


_REPO_ROOT = _find_repo_root()
_SCRIPT = _REPO_ROOT / "scripts" / "check_cadence.py"


def run_script(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """check_cadence.py を subprocess で実行してCompletedProcessを返す."""
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd is not None else None,
    )


class TestCheckCadenceCleanWorktree:
    """uncommitted 変更なし（クリーンな状態）のテスト."""

    def test_clean_worktree_exits_zero(self, tmp_path: Path) -> None:
        """git init したクリーンな worktree では exit 0 を返す."""
        # 空の git リポジトリを作成して初期コミットを作る
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        (tmp_path / "README.md").write_text("initial")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        result = run_script("--worktree", str(tmp_path))
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"

    def test_clean_worktree_prints_ok(self, tmp_path: Path) -> None:
        """クリーンな状態では 'OK:' を含む出力を返す."""
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        (tmp_path / "README.md").write_text("initial")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        result = run_script("--worktree", str(tmp_path))
        assert "OK" in result.stdout


class TestCheckCadenceFilesThreshold:
    """ファイル数の閾値チェックのテスト."""

    def _make_git_repo_with_uncommitted_files(
        self, tmp_path: Path, n_files: int, lines_per_file: int = 1
    ) -> None:
        """n_files 個の未コミットファイルを持つ git リポジトリを作る."""
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        (tmp_path / "README.md").write_text("initial")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        # uncommitted files を作成（add しない）
        for i in range(n_files):
            content = "\n".join([f"line_{j}" for j in range(lines_per_file)])
            (tmp_path / f"new_file_{i}.py").write_text(content)

    def test_below_files_threshold_exits_zero(self, tmp_path: Path) -> None:
        """デフォルト閾値(5ファイル)未満では exit 0."""
        self._make_git_repo_with_uncommitted_files(tmp_path, n_files=4)
        result = run_script("--worktree", str(tmp_path))
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"

    def test_at_files_threshold_exits_zero(self, tmp_path: Path) -> None:
        """デフォルト閾値(5ファイル)ちょうどは exit 0（超過でない）."""
        self._make_git_repo_with_uncommitted_files(tmp_path, n_files=5)
        result = run_script("--worktree", str(tmp_path))
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"

    def test_above_files_threshold_exits_one(self, tmp_path: Path) -> None:
        """デフォルト閾値(5ファイル)超過では exit 1."""
        self._make_git_repo_with_uncommitted_files(tmp_path, n_files=6)
        result = run_script("--worktree", str(tmp_path))
        assert result.returncode == 1, f"stdout: {result.stdout}\nstderr: {result.stderr}"

    def test_above_files_threshold_prints_warning(self, tmp_path: Path) -> None:
        """ファイル数超過では警告メッセージを出力する."""
        self._make_git_repo_with_uncommitted_files(tmp_path, n_files=6)
        result = run_script("--worktree", str(tmp_path))
        assert "WARNING" in result.stdout or "WARN" in result.stdout.upper()

    def test_custom_files_threshold(self, tmp_path: Path) -> None:
        """--threshold-files で閾値変更できる."""
        self._make_git_repo_with_uncommitted_files(tmp_path, n_files=3)
        # デフォルト(5)では OK だが、閾値を 2 にすると NG になる
        result = run_script("--worktree", str(tmp_path), "--threshold-files", "2")
        assert result.returncode == 1, f"stdout: {result.stdout}\nstderr: {result.stderr}"


class TestCheckCadenceLinesThreshold:
    """追加行数の閾値チェックのテスト."""

    def _make_git_repo_with_large_file(self, tmp_path: Path, n_lines: int) -> None:
        """n_lines 行の未コミットファイルを持つ git リポジトリを作る."""
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        (tmp_path / "README.md").write_text("initial")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        content = "\n".join([f"line_{i}" for i in range(n_lines)])
        (tmp_path / "large_file.py").write_text(content)

    def test_below_lines_threshold_exits_zero(self, tmp_path: Path) -> None:
        """デフォルト閾値(200行)未満では exit 0."""
        self._make_git_repo_with_large_file(tmp_path, n_lines=100)
        result = run_script("--worktree", str(tmp_path))
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"

    def test_above_lines_threshold_exits_one(self, tmp_path: Path) -> None:
        """デフォルト閾値(200行)超過では exit 1."""
        self._make_git_repo_with_large_file(tmp_path, n_lines=201)
        result = run_script("--worktree", str(tmp_path))
        assert result.returncode == 1, f"stdout: {result.stdout}\nstderr: {result.stderr}"

    def test_custom_lines_threshold(self, tmp_path: Path) -> None:
        """--threshold-lines で閾値変更できる."""
        self._make_git_repo_with_large_file(tmp_path, n_lines=50)
        result = run_script("--worktree", str(tmp_path), "--threshold-lines", "30")
        assert result.returncode == 1, f"stdout: {result.stdout}\nstderr: {result.stderr}"


class TestCheckCadenceOutput:
    """出力フォーマットのテスト."""

    def _make_clean_repo(self, tmp_path: Path) -> None:
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        (tmp_path / "README.md").write_text("initial")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

    def test_ok_output_contains_files_count(self, tmp_path: Path) -> None:
        """OK 時の出力に files 数が含まれる."""
        self._make_clean_repo(tmp_path)
        result = run_script("--worktree", str(tmp_path))
        assert "files" in result.stdout.lower() or "file" in result.stdout.lower()

    def test_ok_output_contains_lines_count(self, tmp_path: Path) -> None:
        """OK 時の出力に lines 数が含まれる."""
        self._make_clean_repo(tmp_path)
        result = run_script("--worktree", str(tmp_path))
        assert "line" in result.stdout.lower()
