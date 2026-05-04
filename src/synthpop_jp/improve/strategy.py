"""Improvement strategies (Issue #119).

改善ループ（spec §14）の戦略を 3 種類実装する。

- :class:`RandomSearchStrategy`: ベースライン下限。``param_ranges`` から一様サンプリング
- :class:`RuleBasedStrategy`: spec §14.3 の if-then ルール
- :class:`ParetoStrategy`: spec §14.4 の 3 目的 non-dominated set ベース

すべて :class:`ImproveStrategy` Protocol に従う。``next_config(history)`` を呼ぶと
次の trial で使う :class:`Settings` を返す。

設計方針
--------
- 改善対象は最小で ``p_change`` / ``evals_per_agent`` / ``alpha`` / ``transition_kind``
  の 4 軸に絞る（spec §14.2 の追加軸は将来 Issue で拡張）
- 乱数源は constructor で受け取った ``seed`` を ``np.random.default_rng`` に渡し、
  プロセス内 state に依存しない（同一 seed × 同一 base_settings で決定論的）
- ``Settings`` 自身は immutable に扱い、``model_copy(update=...)`` で派生させる
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable

import numpy as np

from synthpop_jp.config import AnnealingConfig, Settings

if TYPE_CHECKING:
    from synthpop_jp.improve.runner import TrialResult


# 改善対象パラメータの既定範囲。
# - p_change: hybrid 遷移で AgeChange を選ぶ確率
# - evals_per_agent: SA の停止条件（1 person あたりの評価回数）
# - alpha: 指数冷却の冷却率
DEFAULT_PARAM_RANGES: dict[str, tuple[float, float]] = {
    "p_change": (0.1, 0.9),
    "evals_per_agent": (10, 200),
    "alpha": (0.95, 0.9995),
}

# transition_kind の候補。spec §12.2A/B/C の 3 種から選ぶ。
DEFAULT_TRANSITION_CHOICES: tuple[str, ...] = ("age-change", "age-swap", "hybrid")


@runtime_checkable
class ImproveStrategy(Protocol):
    """改善戦略の最小 Protocol.

    Methods
    -------
    next_config(history)
        これまでの trial 結果を見て、次の trial で使う :class:`Settings` を返す。
    """

    def next_config(self, history: Sequence[TrialResult]) -> Settings:
        """次の trial 用の Settings を返す."""
        ...


def _apply_annealing_overrides(
    base: Settings,
    *,
    p_change: float,
    evals_per_agent: int,
    alpha: float,
    transition_kind: str,
) -> Settings:
    """改善対象 4 軸を base settings に当てて新しい Settings を返す.

    transition_kind が ``"hybrid"`` のときは ``p_change + p_swap == 1.0`` を満たす
    ``p_swap`` を自動計算する（constant schedule）。
    """
    annealing_kwargs: dict[str, object] = {
        "T0": base.annealing.T0,
        "alpha": float(alpha),
        "max_iters": base.annealing.max_iters,
        "evals_per_agent": int(evals_per_agent),
        "target_threshold": base.annealing.target_threshold,
        "patience": base.annealing.patience,
        "log_every_n_iters": base.annealing.log_every_n_iters,
        "trace_enabled": base.annealing.trace_enabled,
        "checkpoint_every_n_iters": base.annealing.checkpoint_every_n_iters,
        "checkpoint_dir": base.annealing.checkpoint_dir,
        "transition_kind": transition_kind,
        "p_change": float(p_change),
        "p_swap": 1.0 - float(p_change),
        "p_change_schedule": "constant",
        "p_change_end": None,
    }
    new_annealing = AnnealingConfig(**annealing_kwargs)  # type: ignore[arg-type]
    return base.model_copy(update={"annealing": new_annealing})


class RandomSearchStrategy:
    """ベースライン下限。``param_ranges`` から一様サンプリング.

    Parameters
    ----------
    base_settings : Settings
        改変前の Settings。``annealing`` の改善対象 4 軸が trial ごとに上書きされる。
    seed : int
        乱数 seed。同一 seed × 同一 base_settings で next_config 列が決定論的になる。
    param_ranges : dict[str, tuple[float, float]] | None
        ``"p_change"`` / ``"evals_per_agent"`` / ``"alpha"`` の各パラメータの
        ``(low, high)`` 範囲。省略時は :data:`DEFAULT_PARAM_RANGES`。
    transition_choices : Sequence[str] | None
        transition_kind の候補。省略時は :data:`DEFAULT_TRANSITION_CHOICES`。
    """

    def __init__(
        self,
        base_settings: Settings,
        *,
        seed: int = 42,
        param_ranges: dict[str, tuple[float, float]] | None = None,
        transition_choices: Sequence[str] | None = None,
    ) -> None:
        self._base = base_settings
        self._rng = np.random.default_rng(seed)
        if param_ranges is not None:
            self._ranges = dict(param_ranges)
        else:
            self._ranges = dict(DEFAULT_PARAM_RANGES)
        self._transition_choices: tuple[str, ...] = tuple(
            transition_choices if transition_choices is not None else DEFAULT_TRANSITION_CHOICES
        )

    def next_config(self, history: Sequence[TrialResult]) -> Settings:
        """History を無視し、param_ranges から一様サンプル."""
        del history  # baseline strategy は履歴を参照しない
        p_low, p_high = self._ranges["p_change"]
        e_low, e_high = self._ranges["evals_per_agent"]
        a_low, a_high = self._ranges["alpha"]

        p_change = float(self._rng.uniform(p_low, p_high))
        # evals_per_agent は整数。範囲は inclusive にする。
        evals = int(self._rng.integers(int(e_low), int(e_high) + 1))
        alpha = float(self._rng.uniform(a_low, a_high))
        n_choices = len(self._transition_choices)
        transition_kind = str(self._transition_choices[int(self._rng.integers(0, n_choices))])

        return _apply_annealing_overrides(
            self._base,
            p_change=p_change,
            evals_per_agent=evals,
            alpha=alpha,
            transition_kind=transition_kind,
        )


# --- Step 2 / 4 で実装される戦略は同ファイル内に追記する想定 ---


# ルール発火の閾値。spec §14.3 の if-then ルールを最小実装として落とし込む。
RULE_PARENT_CHILD_L1_THRESHOLD = 1.0
RULE_DEMOGRAPHIC_L1_THRESHOLD = 0.5
RULE_UNIQUE_RATE_THRESHOLD = 0.3
RULE_SLOW_CONVERGENCE_THRESHOLD = 0.3  # improvement < 30% → 収束遅
# 各ルールが 1 trial あたりに動かす量。微調整で発散しないよう保守的に。
RULE_P_CHANGE_DELTA = 0.1
RULE_EVALS_FACTOR = 0.7  # rare cell unique 高 → evals を 0.7 倍
RULE_EVALS_FLOOR = 5  # evals_per_agent はこの値より下げない
RULE_ALPHA_DELTA = 0.001
RULE_ALPHA_CEIL = 0.9999  # alpha は 1.0 ぴったりにしない（冷却が止まるため）


class RuleBasedStrategy:
    """spec §14.3 の if-then ルールベース改善戦略.

    history の **直近 trial の metrics** を見て次の config を決定する純粋関数。
    history が空のときは ``base_settings`` をそのまま返す。

    対応するルール:

    1. 親子年齢差 L1 が大きい → ``p_change`` 上昇（age-change 比率を上げる）
    2. demographic 小だが親族関係大 → ``p_change`` 低下（age-swap 比率を上げる）
    3. rare cell unique 率高 → ``evals_per_agent`` 減少（過学習を避ける）
    4. 収束遅（improvement < 30%）→ ``alpha`` 上昇（温度減衰を緩める）

    Parameters
    ----------
    base_settings : Settings
        改変前の Settings。各ルールはこの annealing を起点として差分を加える。
    seed : int
        本戦略は決定論的なので seed は使われないが、API 一貫性のため受け取る。
    """

    def __init__(self, base_settings: Settings, *, seed: int = 42) -> None:
        del seed  # 本戦略は乱数を使わない
        self._base = base_settings

    def next_config(self, history: Sequence[TrialResult]) -> Settings:
        """直近 trial のメトリクスから 4 ルールを順番に適用."""
        if not history:
            return self._base

        latest = history[-1]
        m = latest.metrics

        # 現在の改善対象 4 軸の値（base から開始し、ルールで上書きする）
        ann = self._base.annealing
        p_change = float(ann.p_change)
        evals_per_agent = int(ann.evals_per_agent)
        alpha = float(ann.alpha)
        transition_kind = ann.transition_kind

        # ルール 1 / 2: parent_child / demographic の比較で p_change を動かす
        pc_l1 = float(m.get("aggregate.l1.parent_child", 0.0))
        demo_l1 = float(m.get("aggregate.l1.demographic", 0.0))
        if pc_l1 > RULE_PARENT_CHILD_L1_THRESHOLD:
            # 親子年齢差大 → age-change を増やす
            p_change = min(1.0, p_change + RULE_P_CHANGE_DELTA)
        elif demo_l1 < RULE_DEMOGRAPHIC_L1_THRESHOLD and pc_l1 > demo_l1 * 2.0:
            # demographic 小だが親族関係（ここでは parent_child の相対大）大 → age-swap を増やす
            p_change = max(0.0, p_change - RULE_P_CHANGE_DELTA)

        # ルール 3: rare cell unique 率が高い → evals_per_agent を下げる
        unique_rate = float(m.get("rare_cell.unique_rate", 0.0))
        if unique_rate > RULE_UNIQUE_RATE_THRESHOLD:
            evals_per_agent = max(RULE_EVALS_FLOOR, int(evals_per_agent * RULE_EVALS_FACTOR))

        # ルール 4: improvement < 30% → alpha を上げて冷却を緩める
        initial = float(m.get("initial_score", 0.0))
        best = float(m.get("best_score", 0.0))
        if initial > 0.0:
            improvement = 1.0 - best / initial
            if improvement < RULE_SLOW_CONVERGENCE_THRESHOLD:
                alpha = min(RULE_ALPHA_CEIL, alpha + RULE_ALPHA_DELTA)

        return _apply_annealing_overrides(
            self._base,
            p_change=p_change,
            evals_per_agent=evals_per_agent,
            alpha=alpha,
            transition_kind=transition_kind,
        )


RuleName = Literal["large_parent_child_l1", "high_unique_rate", "slow_convergence"]
