"""Multi-trial improvement loop runner (Issue #119).

``run_improve_loop`` は base_settings に対して n_trials 回の SA を回し、
各 trial の合成人口と評価指標を ``output_root/<run_id>/trial_NNN/`` に書き出す。

戦略は :class:`~synthpop_jp.improve.strategy.ImproveStrategy` を満たす任意の
オブジェクトを受け取る。文字列名（``"rule_based"`` / ``"pareto"`` /
``"random_search"``）でも切り替えできる（:func:`build_strategy`）。

決定性
------
同一 ``base_settings`` × 同一 ``strategy_name`` × 同一 ``seed`` で 2 回呼ぶと、
``best_config.yaml`` が bitwise 一致する（spec §19.3）。

実装は段階的に積む（Issue #119 plan 参照）。Step 5 で ``run_improve_loop``
本体を追加する。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from synthpop_jp.config import Settings


StrategyName = Literal["rule_based", "pareto", "random_search"]
ObjectiveName = Literal["composite", "statistical_fit", "utility", "privacy"]


@dataclass(frozen=True)
class TrialResult:
    """1 trial の結果.

    Attributes
    ----------
    trial_id : int
        1-origin の trial 番号。
    config : Settings
        この trial で使った Settings。
    metrics : dict[str, float]
        評価指標。最低限 ``best_score`` を含む。3 目的の代理指標として
        ``statistical_fit`` / ``utility`` / ``privacy`` の正規化済み値も入れる。
    elapsed_s : float
        この trial の壁時計時間（秒）。
    output_dir : Path | None
        この trial の成果物を書き出したディレクトリ。dry_run 時は ``None``。
    """

    trial_id: int
    config: Settings
    metrics: dict[str, float] = field(default_factory=lambda: dict[str, float]())
    elapsed_s: float = 0.0
    output_dir: Path | None = None


@dataclass(frozen=True)
class ImproveLoopResult:
    """改善ループ全体の結果.

    Attributes
    ----------
    run_id : str
        この run の ID（出力ディレクトリ名に使う）。
    history : list[TrialResult]
        各 trial の結果。
    best : TrialResult
        composite objective での best trial。
    output_dir : Path
        ``outputs/improve/<run_id>/`` のパス。
    """

    run_id: str
    history: list[TrialResult]
    best: TrialResult
    output_dir: Path


__all__ = [
    "ImproveLoopResult",
    "ObjectiveName",
    "StrategyName",
    "TrialResult",
]
