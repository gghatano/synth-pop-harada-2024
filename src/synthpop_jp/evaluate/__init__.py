"""Evaluator suite (Phase 3.5 / Phase 4 で実体).

提供する Evaluator 一覧（Phase 3.5 時点）
----------------------------------------
- :class:`~synthpop_jp.evaluate.aggregate_metrics.AggregateStatL1Evaluator`
  (Issue #59): 統計別 L1 誤差レポータ
- :class:`~synthpop_jp.evaluate.rare_cell_metrics.RareCellEvaluator`
  (Issue #61): (family_type, age) cell の rare/unique 率
- :class:`~synthpop_jp.evaluate.attribute_inference.CAPEvaluator`
  (Issue #65): Generalized CAP / TCAP の attribute inference baseline
"""

from synthpop_jp.evaluate.aggregate_metrics import AggregateStatL1Evaluator
from synthpop_jp.evaluate.attribute_inference import CAPEvaluator
from synthpop_jp.evaluate.rare_cell_metrics import RareCellEvaluator

__all__ = ["AggregateStatL1Evaluator", "CAPEvaluator", "RareCellEvaluator"]
