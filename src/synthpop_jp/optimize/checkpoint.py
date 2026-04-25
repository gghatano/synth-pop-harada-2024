"""SA 実行状態のチェックポイント保存・読み込み — Issue #32.

SA（シミュレーテッドアニーリング）の実行状態を pickle + gzip 形式で保存・復元するモジュール。

長時間の SA 実行が OS 再起動・CI タイムアウトなどで中断されたとき、
``--resume`` オプションで直近のチェックポイントから再開できるようにする。

保存対象
--------
- ``SAState``: 反復数・スコア・受理数
- ``PopulationArrays``: 現在の人口配列（numpy 配列全フィールド）
- ``ObjectiveState``: ヒストグラムと total_score（StatTable のリスト）
- ``best_arrays``: best_score 達成時の人口配列
- ``best_score``: 最良スコア
- ``rng_state``: numpy Generator の bit_generator 状態（再開時の乱数再現に必須）

保存形式
--------
**pickle + gzip (.pkl.gz)** を採用。

Parquet（列志向形式）は PopulationArrays の numpy 配列と相性が良いが、
ObjectiveState の StatTable リスト（ヒストグラム + bin_edges の複合構造体）を
Parquet テーブルに変換するには変換 logic が複雑になる。
pickle ならワンショットで全状態をシリアライズでき、1000 世帯規模で < 100ms の
I/O 要件を満たせる。将来 Issue #33 の benchmark で要件が明確になったら
Parquet 化を検討する（Issue #32 のコメントに記録済）。

チェックポイントファイル構成
----------------------------
::

    outputs/<run>/artifacts/checkpoint/
        iter_10000.pkl.gz
        iter_20000.pkl.gz
        latest.pkl.gz  (最新チェックポイントのコピー)

``latest.pkl.gz`` はシンボリックリンクではなく最新コピーとする（OS 互換性のため）。

使い方
------
::

    from pathlib import Path
    from synthpop_jp.optimize.checkpoint import save_checkpoint, load_checkpoint

    # 保存
    save_checkpoint(
        state=sa_state,
        arrays=arrays,
        objective_state=objective,
        best_arrays=best_arrays,
        best_score=42.0,
        rng_state=rng.bit_generator.state,
        path=Path("artifacts/checkpoint/iter_10000.pkl.gz"),
    )

    # 復元
    state, arrays, objective, best_arrays, best_score, rng_state = load_checkpoint(
        Path("artifacts/checkpoint/latest.pkl.gz")
    )
    rng.bit_generator.state = rng_state
"""

from __future__ import annotations

import gzip
import pickle
from pathlib import Path
from typing import Any

from synthpop_jp.optimize.annealing import SAState
from synthpop_jp.optimize.objective import ObjectiveState, StatTable
from synthpop_jp.optimize.state import PopulationArrays


def save_checkpoint(
    *,
    state: SAState,
    arrays: PopulationArrays,
    objective_state: ObjectiveState,
    best_arrays: PopulationArrays,
    best_score: float,
    rng_state: dict[str, Any],
    path: Path,
) -> None:
    """SA の現在状態をチェックポイントファイルに保存する.

    pickle + gzip 形式（.pkl.gz）で保存する。
    保存先ディレクトリが存在しない場合は自動作成する。

    Parameters
    ----------
    state : SAState
        SA の現在状態（反復数・スコア・受理数）。
    arrays : PopulationArrays
        現在の人口配列。
    objective_state : ObjectiveState
        目的関数の状態（ヒストグラム + total_score）。
    best_arrays : PopulationArrays
        best_score 達成時の人口配列。
    best_score : float
        これまでの最良スコア。
    rng_state : dict[str, Any]
        numpy Generator の bit_generator 状態。
        ``rng.bit_generator.state`` で取得する。
    path : Path
        書き出し先のファイルパス（.pkl.gz を推奨）。

    Examples
    --------
    >>> import numpy as np
    >>> from pathlib import Path
    >>> import tempfile
    >>> from synthpop_jp.optimize.annealing import SAState
    >>> from synthpop_jp.optimize.objective import ObjectiveState
    >>> from synthpop_jp.optimize.state import PopulationArrays
    >>> from synthpop_jp.domain.registry import FamilyTypeRegistry, RoleRegistry, SexRegistry
    >>> family_reg = FamilyTypeRegistry(); role_reg = RoleRegistry(); sex_reg = SexRegistry()
    >>> arrays = PopulationArrays.empty(family_reg, role_reg, sex_reg)
    >>> objective = ObjectiveState(arrays=arrays, stats=[], total_score=0.0)
    >>> best_arrays = PopulationArrays.empty(family_reg, role_reg, sex_reg)
    >>> rng = np.random.default_rng(0)
    >>> state = SAState()
    >>> with tempfile.NamedTemporaryFile(suffix=".pkl.gz") as f:
    ...     save_checkpoint(
    ...         state=state, arrays=arrays, objective_state=objective,
    ...         best_arrays=best_arrays, best_score=0.0,
    ...         rng_state=rng.bit_generator.state, path=Path(f.name)
    ...     )
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _make_payload(
        state=state,
        arrays=arrays,
        objective_state=objective_state,
        best_arrays=best_arrays,
        best_score=best_score,
        rng_state=rng_state,
    )
    with gzip.open(path, "wb") as fh:
        pickle.dump(payload, fh, protocol=pickle.HIGHEST_PROTOCOL)


def load_checkpoint(
    path: Path,
) -> tuple[SAState, PopulationArrays, ObjectiveState, PopulationArrays, float, dict[str, Any]]:
    """チェックポイントファイルから SA の状態を復元する.

    Parameters
    ----------
    path : Path
        読み込むチェックポイントファイルのパス（.pkl.gz）。

    Returns
    -------
    tuple[SAState, PopulationArrays, ObjectiveState, PopulationArrays, float, dict]
        ``(state, arrays, objective_state, best_arrays, best_score, rng_state)``

        - ``state``: SA の状態（反復数・スコア・受理数）
        - ``arrays``: 復元された人口配列
        - ``objective_state``: 復元された目的関数状態
        - ``best_arrays``: best_score 達成時の人口配列
        - ``best_score``: 最良スコア
        - ``rng_state``: numpy Generator の bit_generator 状態

    Raises
    ------
    FileNotFoundError
        ファイルが存在しない場合。

    Examples
    --------
    >>> import numpy as np
    >>> from pathlib import Path
    >>> import tempfile
    >>> from synthpop_jp.optimize.annealing import SAState
    >>> from synthpop_jp.optimize.objective import ObjectiveState
    >>> from synthpop_jp.optimize.state import PopulationArrays
    >>> from synthpop_jp.domain.registry import FamilyTypeRegistry, RoleRegistry, SexRegistry
    >>> family_reg = FamilyTypeRegistry(); role_reg = RoleRegistry(); sex_reg = SexRegistry()
    >>> arrays = PopulationArrays.empty(family_reg, role_reg, sex_reg)
    >>> objective = ObjectiveState(arrays=arrays, stats=[], total_score=0.0)
    >>> best_arrays = PopulationArrays.empty(family_reg, role_reg, sex_reg)
    >>> rng = np.random.default_rng(0)
    >>> state = SAState()
    >>> with tempfile.NamedTemporaryFile(suffix=".pkl.gz", delete=False) as f:
    ...     tmp_path = Path(f.name)
    >>> save_checkpoint(
    ...     state=state, arrays=arrays, objective_state=objective,
    ...     best_arrays=best_arrays, best_score=0.0,
    ...     rng_state=rng.bit_generator.state, path=tmp_path
    ... )
    >>> loaded = load_checkpoint(tmp_path)
    >>> loaded[0].iter
    0
    >>> tmp_path.unlink()
    """
    with gzip.open(path, "rb") as fh:
        payload: dict[str, Any] = pickle.load(fh)  # noqa: S301
    return _restore_from_payload(payload)


# ---------------------------------------------------------------------------
# 内部ヘルパー
# ---------------------------------------------------------------------------


def _make_payload(
    *,
    state: SAState,
    arrays: PopulationArrays,
    objective_state: ObjectiveState,
    best_arrays: PopulationArrays,
    best_score: float,
    rng_state: dict[str, Any],
) -> dict[str, Any]:
    """保存用 dict を構築する."""
    return {
        "state": {
            "iter": state.iter,
            "current_score": state.current_score,
            "best_score": state.best_score,
            "n_accepted": state.n_accepted,
            "n_total": state.n_total,
        },
        "arrays": _serialize_population_arrays(arrays),
        "objective_state": _serialize_objective_state(objective_state),
        "best_arrays": _serialize_population_arrays(best_arrays),
        "best_score": best_score,
        "rng_state": rng_state,
    }


def _restore_from_payload(
    payload: dict[str, Any],
) -> tuple[SAState, PopulationArrays, ObjectiveState, PopulationArrays, float, dict[str, Any]]:
    """dict から状態を復元する."""
    state_dict = payload["state"]
    state = SAState(
        iter=state_dict["iter"],
        current_score=state_dict["current_score"],
        best_score=state_dict["best_score"],
        n_accepted=state_dict["n_accepted"],
        n_total=state_dict["n_total"],
    )
    arrays = _deserialize_population_arrays(payload["arrays"])
    objective_state = _deserialize_objective_state(payload["objective_state"], arrays)
    best_arrays = _deserialize_population_arrays(payload["best_arrays"])
    best_score: float = payload["best_score"]
    rng_state: dict[str, Any] = payload["rng_state"]
    return state, arrays, objective_state, best_arrays, best_score, rng_state


def _serialize_population_arrays(arrays: PopulationArrays) -> dict[str, Any]:
    """PopulationArrays を dict にシリアライズする."""
    return {
        "age": arrays.age,
        "sex": arrays.sex,
        "role": arrays.role,
        "household_id": arrays.household_id,
        "family_type": arrays.family_type,
        "family_reg": arrays._family_reg,
        "role_reg": arrays._role_reg,
        "sex_reg": arrays._sex_reg,
    }


def _deserialize_population_arrays(d: dict[str, Any]) -> PopulationArrays:
    """dict から PopulationArrays を復元する."""
    return PopulationArrays(
        age=d["age"],
        sex=d["sex"],
        role=d["role"],
        household_id=d["household_id"],
        family_type=d["family_type"],
        _family_reg=d["family_reg"],
        _role_reg=d["role_reg"],
        _sex_reg=d["sex_reg"],
    )


def _serialize_objective_state(objective: ObjectiveState) -> dict[str, Any]:
    """ObjectiveState を dict にシリアライズする."""
    stats_data = [
        {
            "observed": st.observed,
            "target": st.target,
            "bin_edges": st.bin_edges,
        }
        for st in objective.stats
    ]
    return {
        "stats": stats_data,
        "total_score": objective.total_score,
    }


def _deserialize_objective_state(
    d: dict[str, Any], arrays: PopulationArrays
) -> ObjectiveState:
    """dict から ObjectiveState を復元する.

    復元された ``ObjectiveState`` の ``arrays`` フィールドは
    引数 ``arrays`` への参照となる（コピーしない）。
    これにより、SARunner が resume 後に apply_change を呼んだとき
    ObjectiveState と arrays が同じオブジェクトを指すことを保証する。
    """
    stats = [
        StatTable(
            observed=item["observed"],
            target=item["target"],
            bin_edges=item["bin_edges"],
        )
        for item in d["stats"]
    ]
    return ObjectiveState(
        arrays=arrays,
        stats=stats,
        total_score=d["total_score"],
    )
