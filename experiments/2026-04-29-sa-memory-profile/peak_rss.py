"""Subprocess RSS sampler with OOM guard — Issue #51.

子プロセスを起動し、外部から ``ps -o rss=`` でピーク RSS を計測するユーティリティ。
RSS が指定閾値を超えた時点で SIGTERM → SIGKILL し、PC が固まる事故を物理的に防ぐ。

新規依存を増やさないため ``psutil`` ではなく POSIX ``ps`` を呼ぶ。
``ps -o rss= -p <pid>`` は Linux/macOS どちらも RSS を 1024 バイト単位で返す。
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PeakRSSResult:
    """Result of a peak-RSS sampled subprocess run.

    Parameters
    ----------
    peak_rss_bytes : int
        Maximum RSS observed across sampling interval, in bytes.
    elapsed_seconds : float
        Wall-clock seconds from spawn to exit/kill.
    oom_killed : bool
        True if the child was terminated by the OOM guard.
    exit_code : int | None
        Exit code if the child exited cleanly; ``None`` if killed by signal.
    """

    peak_rss_bytes: int
    elapsed_seconds: float
    oom_killed: bool
    exit_code: int | None


def _ps_rss_kb(pid: int) -> int | None:
    """Return RSS of ``pid`` in KB, or ``None`` if the process no longer exists."""
    try:
        out = subprocess.check_output(
            ["ps", "-o", "rss=", "-p", str(pid)],
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return None
    text = out.decode().strip()
    if not text:
        return None
    return int(text)


def sample_peak_rss(
    cmd: list[str],
    *,
    sample_interval_seconds: float = 0.1,
    oom_limit_bytes: int | None = None,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    sigterm_grace_seconds: float = 5.0,
) -> PeakRSSResult:
    """Run ``cmd`` as a subprocess and return its peak RSS.

    Parameters
    ----------
    cmd : list[str]
        Command and arguments passed to :class:`subprocess.Popen`.
    sample_interval_seconds : float, optional
        Seconds between successive RSS samples (default ``0.1``).
    oom_limit_bytes : int | None, optional
        If set and observed RSS exceeds it, SIGTERM the child (waits
        ``sigterm_grace_seconds``) then SIGKILL.
    cwd : Path | None, optional
        Working directory for the subprocess.
    env : dict[str, str] | None, optional
        Environment variables for the subprocess.
    sigterm_grace_seconds : float, optional
        Seconds to wait between SIGTERM and SIGKILL (default ``5.0``).

    Returns
    -------
    PeakRSSResult
        Peak RSS, elapsed time, OOM-kill flag, and exit code.
    """
    start = time.monotonic()
    proc = subprocess.Popen(cmd, cwd=cwd, env=env)
    peak_rss_bytes = 0
    oom_killed = False

    try:
        while True:
            rss_kb = _ps_rss_kb(proc.pid)
            if rss_kb is not None:
                peak_rss_bytes = max(peak_rss_bytes, rss_kb * 1024)

            if oom_limit_bytes is not None and peak_rss_bytes > oom_limit_bytes:
                oom_killed = True
                proc.terminate()
                try:
                    proc.wait(timeout=sigterm_grace_seconds)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                break

            if proc.poll() is not None:
                break

            time.sleep(sample_interval_seconds)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()

    elapsed = time.monotonic() - start
    exit_code = proc.returncode if not oom_killed else None
    return PeakRSSResult(
        peak_rss_bytes=peak_rss_bytes,
        elapsed_seconds=elapsed,
        oom_killed=oom_killed,
        exit_code=exit_code,
    )
