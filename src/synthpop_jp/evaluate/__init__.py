"""Evaluator suite (Phase 3.5 / Phase 4 で実体).

提供する Evaluator 一覧（Phase 3.5 時点）
----------------------------------------
- :class:`~synthpop_jp.evaluate.aggregate_metrics.AggregateStatL1Evaluator`
  (Issue #59): 統計別 L1 誤差レポータ
"""

from synthpop_jp.evaluate.aggregate_metrics import AggregateStatL1Evaluator

__all__ = ["AggregateStatL1Evaluator"]
