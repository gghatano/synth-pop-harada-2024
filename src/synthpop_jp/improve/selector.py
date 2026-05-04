"""Best trial selector (Issue #119, Step 5).

``select_best(history, objective)`` は改善ループの全 trial から、指定 objective
で **最小値** を持つ trial を返す。同点なら ``trial_id`` 最小を返す（決定性）。

objective とメトリクスキーの対応:

- ``"composite"`` → ``best_score`` (SA の終了スコア合計; 小さいほど良い)
- ``"statistical_fit"`` → ``statistical_fit`` (3 目的の正規化済み代理値)
- ``"utility"`` → ``utility``
- ``"privacy"`` → ``privacy``

メトリクスが欠けている trial は ``+inf`` 扱い（必ず後ろに来る）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Sequence

    from synthpop_jp.improve.runner import ObjectiveName, TrialResult


# objective 名 → metrics dict のキー
_OBJECTIVE_TO_KEY: Final[dict[str, str]] = {
    "composite": "best_score",
    "statistical_fit": "statistical_fit",
    "utility": "utility",
    "privacy": "privacy",
}


def select_best(history: Sequence[TrialResult], objective: ObjectiveName) -> TrialResult:
    """Return the trial with minimum value for the given objective.

    Parameters
    ----------
    history : Sequence[TrialResult]
        全 trial の結果。空のとき ValueError。
    objective : ObjectiveName
        ``"composite"`` / ``"statistical_fit"`` / ``"utility"`` / ``"privacy"``。

    Returns
    -------
    TrialResult
        最小値を持つ trial。同点なら ``trial_id`` 最小を返す。

    Raises
    ------
    ValueError
        ``history`` が空、または objective が未知のキー。
    """
    if not history:
        msg = "history が空です。少なくとも 1 trial が必要です。"
        raise ValueError(msg)

    if objective not in _OBJECTIVE_TO_KEY:
        msg = f"未知の objective: {objective!r}。期待値: {list(_OBJECTIVE_TO_KEY)}"
        raise ValueError(msg)

    key = _OBJECTIVE_TO_KEY[objective]

    def score(tr: TrialResult) -> float:
        return float(tr.metrics.get(key, float("inf")))

    # min は最初に出現した最小値を返すが、同点で trial_id 最小を保証するため
    # (score, trial_id) のタプルで比較する。
    return min(history, key=lambda tr: (score(tr), tr.trial_id))


__all__ = ["select_best"]
