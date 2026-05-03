"""Tests for scripts/audit_experiments.py (Issue #115 Step 5).

audit_experiments.audit_directory(exp_dir) は以下の観点でチェックする:
- INPUT.md が存在し、`seed:` / `commit_sha:` / `uv_lock_sha256:` の 3 行を含む
- WEIGHT.md が存在し、`light` または `heavy` の 1 行
- run.py または等価のエントリが存在する

戻り値は AuditReport(passed, missing_items)。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from scripts.audit_experiments import AuditReport, audit_directory, main


def _write_input(
    path: Path, *, with_seed: bool = True, with_sha: bool = True, with_uv_lock: bool = True
) -> None:
    lines = ["# 入力データ", "", "テスト用 INPUT.md です。"]
    if with_seed:
        lines.append("seed: 42")
    if with_sha:
        lines.append("commit_sha: abcdef1234")
    if with_uv_lock:
        lines.append("uv_lock_sha256: 1234567890abcdef")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_weight(path: Path, value: str) -> None:
    path.write_text(value + "\n", encoding="utf-8")


def _write_run(path: Path) -> None:
    path.write_text("# stub run.py\n", encoding="utf-8")


def test_audit_passes_when_all_required_fields_present(tmp_path: Path) -> None:
    """seed / commit_sha / uv_lock_sha256 と WEIGHT / run.py が揃えば PASS."""
    exp = tmp_path / "2026-05-04-foo"
    exp.mkdir()
    _write_input(exp / "INPUT.md")
    _write_weight(exp / "WEIGHT.md", "light")
    _write_run(exp / "run.py")

    report = audit_directory(exp)

    assert isinstance(report, AuditReport)
    assert report.passed is True
    assert report.missing == []


def test_audit_fails_when_input_missing(tmp_path: Path) -> None:
    exp = tmp_path / "2026-05-04-foo"
    exp.mkdir()
    _write_weight(exp / "WEIGHT.md", "light")
    _write_run(exp / "run.py")

    report = audit_directory(exp)

    assert report.passed is False
    assert any("INPUT.md" in m for m in report.missing)


def test_audit_fails_on_missing_seed_line(tmp_path: Path) -> None:
    exp = tmp_path / "2026-05-04-foo"
    exp.mkdir()
    _write_input(exp / "INPUT.md", with_seed=False)
    _write_weight(exp / "WEIGHT.md", "light")
    _write_run(exp / "run.py")

    report = audit_directory(exp)

    assert report.passed is False
    assert any("seed" in m.lower() for m in report.missing)


def test_audit_fails_on_missing_commit_sha(tmp_path: Path) -> None:
    exp = tmp_path / "2026-05-04-foo"
    exp.mkdir()
    _write_input(exp / "INPUT.md", with_sha=False)
    _write_weight(exp / "WEIGHT.md", "heavy")
    _write_run(exp / "run.py")

    report = audit_directory(exp)

    assert report.passed is False
    assert any("commit_sha" in m for m in report.missing)


def test_audit_fails_on_missing_uv_lock_sha(tmp_path: Path) -> None:
    exp = tmp_path / "2026-05-04-foo"
    exp.mkdir()
    _write_input(exp / "INPUT.md", with_uv_lock=False)
    _write_weight(exp / "WEIGHT.md", "light")
    _write_run(exp / "run.py")

    report = audit_directory(exp)

    assert report.passed is False
    assert any("uv_lock_sha256" in m for m in report.missing)


def test_audit_fails_on_invalid_weight(tmp_path: Path) -> None:
    exp = tmp_path / "2026-05-04-foo"
    exp.mkdir()
    _write_input(exp / "INPUT.md")
    _write_weight(exp / "WEIGHT.md", "medium")
    _write_run(exp / "run.py")

    report = audit_directory(exp)

    assert report.passed is False
    assert any("WEIGHT.md" in m for m in report.missing)


def test_audit_fails_on_missing_run_py(tmp_path: Path) -> None:
    exp = tmp_path / "2026-05-04-foo"
    exp.mkdir()
    _write_input(exp / "INPUT.md")
    _write_weight(exp / "WEIGHT.md", "light")

    report = audit_directory(exp)

    assert report.passed is False
    assert any("run.py" in m for m in report.missing)


def test_main_returns_exit_code(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """`main(experiments_root)` がレポート集約と exit code を返す."""
    root = tmp_path / "experiments"
    root.mkdir()
    good = root / "2026-05-04-good"
    good.mkdir()
    _write_input(good / "INPUT.md")
    _write_weight(good / "WEIGHT.md", "light")
    _write_run(good / "run.py")

    bad = root / "2026-05-04-bad"
    bad.mkdir()
    _write_weight(bad / "WEIGHT.md", "light")
    _write_run(bad / "run.py")

    rc = main([str(root)])

    assert rc == 1  # bad has missing INPUT.md
    out = capsys.readouterr().out
    assert "2026-05-04-good" in out
    assert "2026-05-04-bad" in out
