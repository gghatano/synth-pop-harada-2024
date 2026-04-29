"""Subprocess RSS sampler with OOM guard — Issue #51.

子プロセスを起動し、外部から ``ps -o rss=`` でピーク RSS を計測するユーティリティ。
RSS が指定閾値を超えた時点で SIGTERM → SIGKILL し、PC が固まる事故を物理的に防ぐ。

実装は次コミット（Green）。本コミットでは API のシグネチャだけ確定して
``NotImplementedError`` を投げる。
"""

from __future__ import annotations

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
    raise NotImplementedError("実装は次コミット（Green）")
