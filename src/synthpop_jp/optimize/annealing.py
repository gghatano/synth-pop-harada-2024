"""Simulated Annealing runner (Issue #30).

SA（シミュレーテッドアニーリング）の中核ループを実装するモジュール。

このモジュールが提供するもの:
- ``metropolis_accept``: Metropolis 受理判定関数
- ``SAState``: SA の現在状態を保持するデータクラス
- ``SAResult``: SA 実行結果（best_arrays, best_score, 履歴など）
- ``SARunner``: SA の主ループを実行するクラス

設計方針（spec §12, §17 準拠）
------------------------------
- 各反復: ``transition.propose()`` → ``objective.propose_change()`` → Metropolis 判定 →
  受理なら ``objective.apply_change()``（内部で arrays.age も更新される）
- ``best_score`` / ``best_arrays`` をスコア改善時のみ更新
- 温度管理は ``CoolingSchedule`` に外注し、将来の LinearCooling 追加を容易にする
- trace / rich.live は Issue #31 のスコープ（本 Issue には含まない）
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from synthpop_jp.optimize.transitions import TransitionError

if TYPE_CHECKING:
    from synthpop_jp.config import AnnealingConfig
    from synthpop_jp.optimize.cooling import CoolingSchedule
    from synthpop_jp.optimize.objective import ObjectiveState
    from synthpop_jp.optimize.state import PopulationArrays
    from synthpop_jp.optimize.transitions import AgeChangeTransition


# ---------------------------------------------------------------------------
# Metropolis 受理判定
# ---------------------------------------------------------------------------


def metropolis_accept(
    *,
    delta: float,
    temperature: float,
    rng: np.random.Generator,
) -> bool:
    """Metropolis 受理判定.

    - delta <= 0 のとき（改善）: 必ず受理
    - delta > 0 のとき（悪化）: 確率 exp(-delta / temperature) で受理

    temperature == 0 のとき delta > 0 は拒否（確率 0）。

    Parameters
    ----------
    delta : float
        スコア差分（new_score - old_score）。
    temperature : float
        現在の SA 温度。
    rng : np.random.Generator
        乱数生成器。

    Returns
    -------
    bool
        True ならこの遷移を受理する。
    """
    if delta <= 0.0:
        return True
    if temperature <= 0.0:
        return False
    prob = np.exp(-delta / temperature)
    return bool(rng.uniform() < prob)


# ---------------------------------------------------------------------------
# SAState
# ---------------------------------------------------------------------------


@dataclass
class SAState:
    """SA の現在状態を保持するデータクラス.

    Attributes
    ----------
    iter : int
        現在の反復回数（0-indexed）。
    current_score : float
        現在のスコア（last accepted）。
    best_score : float
        これまでの最良スコア。
    n_accepted : int
        受理された遷移の数。
    n_total : int
        試行された遷移の総数。
    """

    iter: int = 0
    current_score: float = 0.0
    best_score: float = 0.0
    n_accepted: int = 0
    n_total: int = 0


# ---------------------------------------------------------------------------
# SAResult
# ---------------------------------------------------------------------------


@dataclass
class SAResult:
    """SA 実行結果.

    Attributes
    ----------
    best_arrays : PopulationArrays
        best_score 達成時の人口配列のコピー。
    final_state : SAState
        最終的な SA 状態。
    scores : list[float]
        best_score の更新履歴（初期値を含む単調非増加リスト）。
        更新があった反復のみ記録する。
    """

    best_arrays: PopulationArrays
    final_state: SAState
    scores: list[float] = field(default_factory=lambda: [])


# ---------------------------------------------------------------------------
# SARunner
# ---------------------------------------------------------------------------


class SARunner:
    """SA の主ループを実行するクラス.

    Parameters
    ----------
    rng : np.random.Generator
        SA ループで Metropolis 判定に使う乱数生成器。
        ``SeedRegistry.rng("sa_runner")`` で生成して注入する。

    Examples
    --------
    >>> import numpy as np
    >>> runner = SARunner(rng=np.random.default_rng(42))
    """

    def __init__(self, rng: np.random.Generator) -> None:
        self._rng = rng

    def run(
        self,
        *,
        arrays: PopulationArrays,
        objective: ObjectiveState,
        transition: AgeChangeTransition,
        cooling: CoolingSchedule,
        config: AnnealingConfig,
    ) -> SAResult:
        """SA ループを実行して SAResult を返す.

        Parameters
        ----------
        arrays : PopulationArrays
            最適化対象の人口配列（in-place 更新される）。
        objective : ObjectiveState
            目的関数の状態オブジェクト。``propose_change`` と ``apply_change`` を使う。
        transition : AgeChangeTransition
            遷移演算子。``propose()`` で ``(person_idx, new_age)`` を返す。
        cooling : CoolingSchedule
            冷却スケジュール。``get_temperature(iter)`` で温度を取得する。
        config : AnnealingConfig
            SA の実行パラメータ。

        Returns
        -------
        SAResult
            最良配列・最終状態・スコア履歴を含む実行結果。
        """
        # 初期状態
        initial_score = float(objective.total_score)
        state = SAState(
            iter=0,
            current_score=initial_score,
            best_score=initial_score,
            n_accepted=0,
            n_total=0,
        )
        scores: list[float] = [initial_score]

        # best_arrays は初期状態のコピーを持つ
        best_arrays = copy.deepcopy(arrays)

        # patience 管理
        patience_counter = 0
        prev_best = initial_score

        # evals_per_agent の上限計算
        n_persons = arrays.n_persons
        eval_limit = config.evals_per_agent * n_persons if config.evals_per_agent > 0 else 0

        # 最大反復回数
        max_iters = config.max_iters if config.max_iters > 0 else int(1e18)

        iter_n = 0
        while iter_n < max_iters:
            # evals_per_agent 停止
            if eval_limit > 0 and iter_n >= eval_limit:
                break

            # target_threshold 停止
            if config.target_threshold > 0.0 and state.best_score <= config.target_threshold:
                break

            # patience 停止
            if config.patience > 0 and patience_counter >= config.patience:
                break

            # 温度取得
            temperature = cooling.get_temperature(iter_n)

            # 遷移提案（ハード制約違反で TransitionError が起きたらスキップ）
            try:
                person_idx, new_age = transition.propose()
            except TransitionError:
                iter_n += 1
                state.iter = iter_n
                state.n_total += 1
                patience_counter += 1
                continue

            # 差分スコア計算
            delta = objective.propose_change(person_idx, new_age)

            # Metropolis 受理判定
            accepted = metropolis_accept(delta=delta, temperature=temperature, rng=self._rng)

            state.n_total += 1

            if accepted:
                # 遷移を受理
                objective.apply_change(person_idx, new_age)
                state.n_accepted += 1
                state.current_score = float(objective.total_score)

                # best_score 更新
                if state.current_score < state.best_score:
                    state.best_score = state.current_score
                    best_arrays = copy.deepcopy(arrays)
                    scores.append(state.best_score)

            # patience カウンタ更新
            if state.best_score < prev_best:
                patience_counter = 0
                prev_best = state.best_score
            else:
                patience_counter += 1

            iter_n += 1
            state.iter = iter_n

        state.iter = iter_n
        return SAResult(
            best_arrays=best_arrays,
            final_state=state,
            scores=scores,
        )
