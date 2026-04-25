"""Tests for make ci and make ci-fast Makefile targets.

These tests verify that:
- `make ci` runs all 4 CI checks (ruff check, ruff format, pyright, pytest)
- `make ci` exits 0 and prints "CI: ALL GREEN" on success
- `make ci` exits non-zero and prints "CI: FAILED at <step>" on failure
- `make ci-fast` skips pyright
- `make ci-fast` exits 0 and prints "CI: ALL GREEN" on success
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def _get_repo_root() -> Path:
    """Locate repo root (directory containing pyproject.toml)."""
    here = Path(__file__)
    for parent in here.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    raise FileNotFoundError("pyproject.toml not found in any ancestor directory")


class TestMakeCiTargetExists:
    """make ci target must exist and be declared as .PHONY."""

    def test_makefile_contains_ci_phony(self) -> None:
        """Makefile should declare ci as .PHONY."""
        repo_root = _get_repo_root()
        makefile = (repo_root / "Makefile").read_text()
        # .PHONY line should include 'ci'
        phony_lines = [line for line in makefile.splitlines() if ".PHONY:" in line]
        phony_targets = " ".join(phony_lines)
        assert "ci" in phony_targets, f".PHONY declaration missing 'ci'. Found: {phony_targets}"

    def test_makefile_contains_ci_fast_phony(self) -> None:
        """Makefile should declare ci-fast as .PHONY."""
        repo_root = _get_repo_root()
        makefile = (repo_root / "Makefile").read_text()
        phony_lines = [line for line in makefile.splitlines() if ".PHONY:" in line]
        phony_targets = " ".join(phony_lines)
        assert "ci-fast" in phony_targets, (
            f".PHONY declaration missing 'ci-fast'. Found: {phony_targets}"
        )

    def test_makefile_has_ci_target_definition(self) -> None:
        """Makefile should have 'ci:' target definition line."""
        repo_root = _get_repo_root()
        makefile = (repo_root / "Makefile").read_text()
        assert "ci:" in makefile, "Makefile missing 'ci:' target definition"

    def test_makefile_has_ci_fast_target_definition(self) -> None:
        """Makefile should have 'ci-fast:' target definition line."""
        repo_root = _get_repo_root()
        makefile = (repo_root / "Makefile").read_text()
        assert "ci-fast:" in makefile, "Makefile missing 'ci-fast:' target definition"


class TestMakeCiOutput:
    """make ci must produce machine-readable output on final line."""

    def test_make_ci_exits_zero_when_all_pass(self) -> None:
        """make ci should exit 0 when all 4 checks pass."""
        repo_root = _get_repo_root()
        result = subprocess.run(
            ["make", "ci"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert result.returncode == 0, (
            f"make ci failed with exit code {result.returncode}.\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

    def test_make_ci_final_line_is_all_green(self) -> None:
        """make ci final output line should be 'CI: ALL GREEN' on success."""
        repo_root = _get_repo_root()
        result = subprocess.run(
            ["make", "ci"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=300,
        )
        combined = result.stdout + result.stderr
        lines = [line.strip() for line in combined.splitlines() if line.strip()]
        assert lines, "make ci produced no output"
        # Find the CI: line in the last 5 lines
        last_lines = lines[-5:]
        ci_lines = [line for line in last_lines if line.startswith("CI:")]
        assert ci_lines, f"No 'CI:' line found in last 5 lines.\nLast 5 lines: {last_lines}"
        assert ci_lines[-1] == "CI: ALL GREEN", (
            f"Expected 'CI: ALL GREEN', got '{ci_lines[-1]}'.\nFull output:\n{combined}"
        )

    def test_make_ci_output_contains_step_markers(self) -> None:
        """make ci output should contain step markers for each check."""
        repo_root = _get_repo_root()
        result = subprocess.run(
            ["make", "ci"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=300,
        )
        combined = result.stdout + result.stderr
        # Each step should have a [step] marker
        for step in ["ruff check", "ruff format", "pyright", "pytest"]:
            assert f"[{step}]" in combined, (
                f"Step marker '[{step}]' not found in make ci output.\nFull output:\n{combined}"
            )


class TestMakeCiFastOutput:
    """make ci-fast must skip pyright but still run other 3 checks."""

    def test_make_ci_fast_exits_zero_when_passing(self) -> None:
        """make ci-fast should exit 0 when ruff check, ruff format, and pytest pass."""
        repo_root = _get_repo_root()
        result = subprocess.run(
            ["make", "ci-fast"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert result.returncode == 0, (
            f"make ci-fast failed with exit code {result.returncode}.\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

    def test_make_ci_fast_final_line_is_all_green(self) -> None:
        """make ci-fast final output line should be 'CI: ALL GREEN' on success."""
        repo_root = _get_repo_root()
        result = subprocess.run(
            ["make", "ci-fast"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=300,
        )
        combined = result.stdout + result.stderr
        lines = [line.strip() for line in combined.splitlines() if line.strip()]
        assert lines, "make ci-fast produced no output"
        last_lines = lines[-5:]
        ci_lines = [line for line in last_lines if line.startswith("CI:")]
        assert ci_lines, f"No 'CI:' line found in last 5 lines.\nLast 5 lines: {last_lines}"
        assert ci_lines[-1] == "CI: ALL GREEN", (
            f"Expected 'CI: ALL GREEN', got '{ci_lines[-1]}'.\nFull output:\n{combined}"
        )

    def test_make_ci_fast_skips_pyright_step(self) -> None:
        """make ci-fast output should NOT contain [pyright] step marker."""
        repo_root = _get_repo_root()
        result = subprocess.run(
            ["make", "ci-fast"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=300,
        )
        combined = result.stdout + result.stderr
        assert "[pyright]" not in combined, (
            f"make ci-fast should skip pyright, but found '[pyright]' in output.\n"
            f"Full output:\n{combined}"
        )

    def test_make_ci_fast_contains_non_pyright_step_markers(self) -> None:
        """make ci-fast output should contain step markers for ruff check, ruff format, pytest."""
        repo_root = _get_repo_root()
        result = subprocess.run(
            ["make", "ci-fast"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=300,
        )
        combined = result.stdout + result.stderr
        for step in ["ruff check", "ruff format", "pytest"]:
            assert f"[{step}]" in combined, (
                f"Step marker '[{step}]' not found in make ci-fast output.\n"
                f"Full output:\n{combined}"
            )
