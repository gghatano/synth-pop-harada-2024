"""Simulated Annealing runner (Issue #30, #31).

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
- trace.jsonl 書き出し（Issue #31）: ``config.trace_enabled=True`` かつ ``trace_path`` 指定時に有効
- rich.Progress 進捗バー（Issue #31）: ``progress_enabled=True`` のとき有効
"""

from __future__ import annotations

import copy
import datetime
import types
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from synthpop_jp.optimize.transitions import AgeSwapTransition, TransitionError

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from rich.progress import Progress, TaskID

    from synthpop_jp.config import AnnealingConfig
    from synthpop_jp.optimize.cooling import CoolingSchedule
    from synthpop_jp.optimize.objective import ObjectiveState
    from synthpop_jp.optimize.state import PopulationArrays
    from synthpop_jp.optimize.transitions import AgeChangeTransition


# ---------------------------------------------------------------------------
# 内部ヘルパー
# ---------------------------------------------------------------------------


class _NullWriter:
    """trace が無効のときに TraceWriter の代替として使う null オブジェクト."""

    def __enter__(self) -> _NullWriter:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        pass

    def write(self, event: object) -> None:
        """何もしない."""


def _build_progress(
    *,
    max_iters: int,
    eval_limit: int,
    enabled: bool,
) -> _NullProgressCtx | _RichProgressCtx:
    """rich.Progress コンテキストマネージャを作る.

    ``enabled=False`` のとき null オブジェクトを返す。
    """
    if not enabled:
        return _NullProgressCtx()
    return _RichProgressCtx(max_iters=max_iters, eval_limit=eval_limit)


class _NullProgressCtx:
    """progress_enabled=False のときに使う null コンテキスト."""

    def __enter__(self) -> None:
        return None

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        pass


class _RichProgressCtx:
    """rich.Progress を wrap するコンテキストマネージャ."""

    def __init__(self, *, max_iters: int, eval_limit: int) -> None:
        self._total = eval_limit if eval_limit > 0 else max_iters
        self._progress: Progress | None = None
        self._task_id: TaskID | None = None

    def __enter__(self) -> tuple[TaskID, Progress]:
        from rich.progress import (
            BarColumn,
            MofNCompleteColumn,
            Progress,
            SpinnerColumn,
            TaskProgressColumn,
            TextColumn,
            TimeElapsedColumn,
            TimeRemainingColumn,
        )

        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]SA最適化[/bold blue]"),
            BarColumn(),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            TextColumn("[green]score:{task.fields[current_score]:.1f}[/green]"),
            TextColumn("[cyan]best:{task.fields[best_score]:.1f}[/cyan]"),
            TextColumn("[yellow]accept:{task.fields[accept_rate]:.3f}[/yellow]"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
        )
        self._progress.__enter__()
        self._task_id = self._progress.add_task(
            "SA",
            total=self._total,
            current_score=0.0,
            best_score=0.0,
            accept_rate=0.0,
        )
        return (self._task_id, self._progress)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        if self._progress is not None:
            self._progress.__exit__(exc_type, exc_val, exc_tb)


# ---------------------------------------------------------------------------
# Metropolis 受理判定
# ---------------------------------------------------------------------------


def _propose_with_apply_callback(
    transition: AgeChangeTransition | AgeSwapTransition,
    objective: ObjectiveState,
) -> tuple[float, Callable[[], None]]:
    """Run ``transition.propose()`` and return ``(delta, apply_callback)``.

    Issue #57: AgeSwapTransition と AgeChangeTransition で propose の戻り値型と
    objective に呼ぶメソッドが異なるため、SA loop 側を 1 経路に保つために本関数で
    分岐を吸収する。``apply_callback`` を呼ぶと変更が atomic に内部状態へ反映される。

    Raises
    ------
    TransitionError
        transition.propose がハード制約違反で諦めた場合。
    """
    if isinstance(transition, AgeSwapTransition):
        (idx_a, age_a_new), (idx_b, age_b_new) = transition.propose()
        delta = objective.propose_swap(idx_a, age_a_new, idx_b, age_b_new)

        def apply_swap() -> None:
            objective.apply_swap(idx_a, age_a_new, idx_b, age_b_new)

        return delta, apply_swap

    person_idx, new_age = transition.propose()
    delta = objective.propose_change(person_idx, new_age)

    def apply_change() -> None:
        objective.apply_change(person_idx, new_age)

    return delta, apply_change


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
        transition: AgeChangeTransition | AgeSwapTransition,
        cooling: CoolingSchedule,
        config: AnnealingConfig,
        trace_path: Path | None = None,
        progress_enabled: bool = True,
        resume_from: Path | None = None,
    ) -> SAResult:
        """SA ループを実行して SAResult を返す.

        Parameters
        ----------
        arrays : PopulationArrays
            最適化対象の人口配列（in-place 更新される）。
            ``resume_from`` を指定した場合、この引数は無視され
            チェックポイントの配列が使われる。
        objective : ObjectiveState
            目的関数の状態オブジェクト。``propose_change`` と ``apply_change`` を使う。
            ``resume_from`` を指定した場合、この引数は無視され
            チェックポイントの状態が使われる。
        transition : AgeChangeTransition
            遷移演算子。``propose()`` で ``(person_idx, new_age)`` を返す。
            ``resume_from`` 指定時も transition は引き続き使用する。
        cooling : CoolingSchedule
            冷却スケジュール。``get_temperature(iter)`` で温度を取得する。
        config : AnnealingConfig
            SA の実行パラメータ。
        trace_path : Path | None
            trace.jsonl の書き出し先パス。``config.trace_enabled=True`` かつ
            ``trace_path`` が指定されている場合のみ書き出す。デフォルト None。
        progress_enabled : bool
            True のとき rich.Progress 進捗バーを表示する。デフォルト True。
            CLI ``--dry-run`` または ``--log-level ERROR`` のとき False を渡す。
        resume_from : Path | None
            再開するチェックポイントファイルのパス（.pkl.gz）。
            指定した場合、``arrays``・``objective``・rng 状態をチェックポイントから復元し、
            チェックポイントの ``iter`` から反復を継続する。デフォルト None。

        Returns
        -------
        SAResult
            最良配列・最終状態・スコア履歴を含む実行結果。
        """
        from synthpop_jp.optimize.checkpoint import load_checkpoint, save_checkpoint
        from synthpop_jp.optimize.trace import TraceEvent, TraceWriter

        # --- resume_from 処理 ---
        # checkpoint から状態を復元する場合は arrays, objective, rng_state を上書きする
        iter_start = 0
        if resume_from is not None:
            (
                ckpt_state,
                arrays,
                objective,
                best_arrays,
                _best_score_loaded,
                rng_state_loaded,
            ) = load_checkpoint(resume_from)
            # rng 状態を復元して乱数列の連続性を保証する
            self._rng.bit_generator.state = rng_state_loaded

            state = SAState(
                iter=ckpt_state.iter,
                current_score=ckpt_state.current_score,
                best_score=ckpt_state.best_score,
                n_accepted=ckpt_state.n_accepted,
                n_total=ckpt_state.n_total,
            )
            scores: list[float] = [state.best_score]
            iter_start = ckpt_state.iter
            prev_best = state.best_score
        else:
            # 初期状態
            initial_score = float(objective.total_score)
            state = SAState(
                iter=0,
                current_score=initial_score,
                best_score=initial_score,
                n_accepted=0,
                n_total=0,
            )
            scores = [initial_score]
            best_arrays = copy.deepcopy(arrays)
            prev_best = initial_score

        # patience 管理
        patience_counter = 0

        # evals_per_agent の上限計算
        n_persons = arrays.n_persons
        eval_limit = config.evals_per_agent * n_persons if config.evals_per_agent > 0 else 0

        # 最大反復回数
        max_iters = config.max_iters if config.max_iters > 0 else int(1e18)

        # trace writer の準備
        use_trace = config.trace_enabled and trace_path is not None
        log_every = config.log_every_n_iters if config.log_every_n_iters > 0 else 1

        # checkpoint の準備
        use_checkpoint = config.checkpoint_every_n_iters > 0 and config.checkpoint_dir is not None
        ckpt_every = config.checkpoint_every_n_iters if use_checkpoint else 0

        # rich.Progress の準備
        _progress_ctx = _build_progress(
            max_iters=max_iters,
            eval_limit=eval_limit,
            enabled=progress_enabled,
        )

        with _progress_ctx as progress_info:
            task_id = progress_info[0] if progress_info is not None else None
            rich_progress = progress_info[1] if progress_info is not None else None

            # 直近 log_every 反復の受理数（受理率計算用）
            recent_accepted = 0

            # trace writer は use_trace のときだけ開く
            writer_ctx: TraceWriter | _NullWriter
            if use_trace and trace_path is not None:
                writer_ctx = TraceWriter(trace_path)
            else:
                writer_ctx = _NullWriter()

            with writer_ctx as writer:
                iter_n = iter_start
                while iter_n < max_iters:
                    # evals_per_agent 停止
                    if eval_limit > 0 and iter_n >= eval_limit:
                        break

                    # target_threshold 停止
                    target_ok = config.target_threshold > 0.0
                    if target_ok and state.best_score <= config.target_threshold:
                        break

                    # patience 停止
                    if config.patience > 0 and patience_counter >= config.patience:
                        break

                    # 温度取得
                    temperature = cooling.get_temperature(iter_n)

                    # 遷移提案（ハード制約違反で TransitionError が起きたらスキップ）
                    # isinstance で型ガードし、delta + apply_callback を 1 経路で組み立てる
                    try:
                        delta, apply_callback = _propose_with_apply_callback(transition, objective)
                    except TransitionError:
                        iter_n += 1
                        state.iter = iter_n
                        state.n_total += 1
                        patience_counter += 1
                        continue

                    # Metropolis 受理判定
                    accepted = metropolis_accept(
                        delta=delta, temperature=temperature, rng=self._rng
                    )

                    state.n_total += 1

                    if accepted:
                        apply_callback()
                        state.n_accepted += 1
                        state.current_score = float(objective.total_score)
                        recent_accepted += 1

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

                    # log_every_n_iters ごとに trace 書き出し + 進捗更新
                    if iter_n % log_every == 0:
                        if use_trace:
                            ts = datetime.datetime.now(datetime.UTC).isoformat()
                            event = TraceEvent(
                                iter=iter_n,
                                temperature=temperature,
                                current_score=state.current_score,
                                best_score=state.best_score,
                                accepted=accepted,
                                delta=delta,
                                timestamp=ts,
                            )
                            writer.write(event)

                        if rich_progress is not None and task_id is not None:
                            accept_rate = recent_accepted / log_every
                            rich_progress.update(
                                task_id,
                                completed=iter_n,
                                current_score=state.current_score,
                                best_score=state.best_score,
                                accept_rate=accept_rate,
                            )
                        recent_accepted = 0

                    # checkpoint_every_n_iters ごとにチェックポイントを保存
                    if use_checkpoint and ckpt_every > 0 and iter_n % ckpt_every == 0:
                        ckpt_dir = config.checkpoint_dir
                        assert ckpt_dir is not None  # use_checkpoint が True なら保証
                        ckpt_path = ckpt_dir / f"iter_{iter_n}.pkl.gz"
                        save_checkpoint(
                            state=state,
                            arrays=arrays,
                            objective_state=objective,
                            best_arrays=best_arrays,
                            best_score=state.best_score,
                            rng_state=self._rng.bit_generator.state,
                            path=ckpt_path,
                        )
                        # latest.pkl.gz を最新コピーとして保存
                        latest_path = ckpt_dir / "latest.pkl.gz"
                        import shutil

                        shutil.copy2(ckpt_path, latest_path)

        state.iter = iter_n
        return SAResult(
            best_arrays=best_arrays,
            final_state=state,
            scores=scores,
        )
