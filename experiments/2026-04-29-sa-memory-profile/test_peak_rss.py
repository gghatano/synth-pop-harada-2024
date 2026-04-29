"""Tests for the peak-RSS subprocess sampler (Issue #51, Red commit).

実験ユーティリティのテストなので ``tests/`` 直下ではなく実験 dir 内に置く。
明示的にパス指定で起動する: ``uv run pytest experiments/2026-04-29-sa-memory-profile/``
"""

from __future__ import annotations

import sys

from peak_rss import PeakRSSResult, sample_peak_rss


def test_sample_peak_rss_captures_allocation() -> None:
    """既知サイズの bytearray を確保する子プロセスのピーク RSS をサンプリングする."""
    alloc_mb = 100
    code = (
        f"import time;"
        f"b = bytearray({alloc_mb} * 1024 * 1024);"
        f"time.sleep(0.5);"
        # touch every page so the OS actually maps physical pages
        f"_ = sum(b[::1024 * 1024])"
    )
    result = sample_peak_rss([sys.executable, "-c", code])

    assert isinstance(result, PeakRSSResult)
    # peak should at least cover the allocation (interpreter adds more on top)
    assert result.peak_rss_bytes >= alloc_mb * 1024 * 1024
    # sanity upper bound — 3x the allocation is generous
    assert result.peak_rss_bytes <= 3 * alloc_mb * 1024 * 1024
    assert result.oom_killed is False
    assert result.exit_code == 0
    assert result.elapsed_seconds >= 0.4


def test_sample_peak_rss_oom_kill() -> None:
    """OOM 閾値を超える子プロセスは SIGTERM/SIGKILL される."""
    alloc_mb = 200
    limit_mb = 50
    code = (
        f"import time;"
        f"b = bytearray({alloc_mb} * 1024 * 1024);"
        f"_ = sum(b[::1024 * 1024]);"
        f"time.sleep(10.0)"
    )
    result = sample_peak_rss(
        [sys.executable, "-c", code],
        oom_limit_bytes=limit_mb * 1024 * 1024,
        sigterm_grace_seconds=2.0,
    )

    assert result.oom_killed is True
    # the child sleeps 10s; we should kill long before that
    assert result.elapsed_seconds < 8.0
