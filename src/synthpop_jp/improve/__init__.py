"""Improvement loop core (Issue #119).

公開 API:

- :class:`ImproveStrategy`: 改善戦略の Protocol
- :class:`RuleBasedStrategy`: spec §14.3 の if-then ルールベース戦略
- :class:`ParetoStrategy`: spec §14.4 の 3 目的 non-dominated set ベース戦略
- :class:`RandomSearchStrategy`: ベースライン下限（一様サンプリング）
- :func:`run_improve_loop`: multi-trial runner
- :func:`select_best`: best config 選択
- :class:`TrialResult`: 1 trial の結果データクラス

設計の要点は ``docs/spec/spec.md §14`` を参照。
"""

from __future__ import annotations

from synthpop_jp.improve.pareto import extract_non_dominated, is_dominated
from synthpop_jp.improve.runner import ImproveLoopResult, TrialResult
from synthpop_jp.improve.strategy import (
    DEFAULT_PARAM_RANGES,
    DEFAULT_TRANSITION_CHOICES,
    ImproveStrategy,
    ParetoStrategy,
    RandomSearchStrategy,
    RuleBasedStrategy,
)

__all__ = [
    "DEFAULT_PARAM_RANGES",
    "DEFAULT_TRANSITION_CHOICES",
    "ImproveLoopResult",
    "ImproveStrategy",
    "ParetoStrategy",
    "RandomSearchStrategy",
    "RuleBasedStrategy",
    "TrialResult",
    "extract_non_dominated",
    "is_dominated",
]
