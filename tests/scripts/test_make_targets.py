"""Smoke tests for Makefile paper_results targets (Issue #115 Step 4).

`make -n <target>` で各ターゲットが解決でき (exit 0)、想定したコマンドが
出力されることを subprocess で確認する。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _make_dry_run(target: str) -> tuple[int, str]:
    """`make -n <target>` を実行して (returncode, stdout) を返す."""
    proc = subprocess.run(
        ["make", "-n", target],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    return proc.returncode, proc.stdout


def test_make_paper_results_resolves() -> None:
    """`make -n paper-results` が exit 0 で exp01 / exp02 を呼ぶ."""
    rc, out = _make_dry_run("paper-results")
    assert rc == 0, f"make -n paper-results failed: {out}"
    assert "experiment-01-age-change-vs-age-swap" in out
    assert "experiment-02-hybrid-strategy" in out
    assert "--check-tolerance" in out


def test_make_paper_results_exp01_resolves() -> None:
    """`make -n paper-results-exp01` だけでも単独で動く."""
    rc, out = _make_dry_run("paper-results-exp01")
    assert rc == 0
    assert "experiment-01-age-change-vs-age-swap/run.py" in out


def test_make_paper_results_exp02_resolves() -> None:
    """`make -n paper-results-exp02`."""
    rc, out = _make_dry_run("paper-results-exp02")
    assert rc == 0
    assert "experiment-02-hybrid-strategy/run.py" in out


def test_make_paper_results_write_uses_write_expected() -> None:
    """期待値再生成は --write-expected 経由."""
    rc, out = _make_dry_run("paper-results-write")
    assert rc == 0
    assert "--write-expected" in out


def test_make_paper_results_full_uses_full_flag() -> None:
    """フル設定は --full を渡す."""
    rc, out = _make_dry_run("paper-results-full")
    assert rc == 0
    assert "--full" in out


def test_make_audit_experiments_resolves() -> None:
    """`make -n audit-experiments` が解決できる."""
    rc, out = _make_dry_run("audit-experiments")
    assert rc == 0
    assert "audit_experiments.py" in out


def test_make_repro_experiments_resolves() -> None:
    """`make -n repro-experiments` が解決できる."""
    rc, _out = _make_dry_run("repro-experiments")
    assert rc == 0


def test_legacy_paper_target_aliases_paper_results() -> None:
    """旧 `make paper` は paper-results を指すエイリアスとして残す."""
    rc, out = _make_dry_run("paper")
    assert rc == 0
    # paper-results-exp01 / -exp02 のどちらかが出ていれば OK
    assert "experiment-01-age-change-vs-age-swap" in out or "experiment-02-hybrid-strategy" in out
