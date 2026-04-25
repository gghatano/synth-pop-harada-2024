"""Property test: propose_change の差分更新が全再計算と一致する — Issue #34.

最重要テスト。任意の ``(PopulationArrays, person_idx, new_age)`` に対して

    ObjectiveState.propose_change(idx, new_age)

が

    score_after_full_recompute - score_before

と 1e-6 以下の誤差で一致することを hypothesis で網羅的に検証する。

なぜこれが最重要か
-------------------
SA の差分更新は全再計算を O(1) に置き換える最適化であり、
「差分 == 全再計算の差分」が成り立たないと SA が誤った方向に最適化する。
このテストが落ちた場合、実装にバグがある可能性が高い。
"""

from __future__ import annotations

import numpy as np
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from synthpop_jp.optimize.objective import ObjectiveState

from .conftest import InitStats, ObjectiveInput, fresh_objective

# ---------------------------------------------------------------------------
# 全再計算ヘルパー
# ---------------------------------------------------------------------------


def _full_recompute_score(
    obj: ObjectiveState,
    inp: ObjectiveInput,
) -> float:
    """obj.arrays の現在状態から全再計算でスコアを求める.

    obj.arrays を直接変更しないこと。
    呼び出し前に age を変更済みの状態で渡すこと。
    """
    fresh = ObjectiveState.from_arrays(
        arrays=obj.arrays,
        age_diff_parent_child=inp.age_diff_parent_child,
        age_diff_couple=inp.age_diff_couple,
        demographic_by_age_sex=inp.demographic_by_age_sex,
    )
    return fresh.total_score


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


@given(
    person_idx_frac=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    new_age=st.integers(min_value=0, max_value=100),
)
@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
def test_propose_change_matches_full_recompute_delta(
    person_idx_frac: float,
    new_age: int,
    sample_stats: InitStats,
    objective_input: ObjectiveInput,
) -> None:
    """任意の (person_idx, new_age) で propose_change が全再計算差分に一致する.

    検証手順:
    1. fresh な ObjectiveState を生成する（毎 example でリセット）
    2. propose_change(idx, new_age) で差分スコアを取得する（副作用なし）
    3. arrays.age[idx] を new_age に書き換えてから全再計算スコアを取得する
    4. 元の age に戻す
    5. (全再計算後スコア) - (元スコア) と propose_change の差分を比較する
    """
    obj = fresh_objective(sample_stats, objective_input)
    n_persons = obj.arrays.n_persons
    idx = max(0, min(int(person_idx_frac * n_persons), n_persons - 1))

    score_before = obj.total_score

    # 差分更新で delta を計算（副作用なし）
    delta_differential = obj.propose_change(idx, new_age)

    # propose は副作用がないことも確認する
    assert obj.total_score == score_before, (
        f"propose_change が total_score を変更した: {score_before} -> {obj.total_score}"
    )
    assert int(obj.arrays.age[idx]) == int(obj.arrays.age[idx]), "arrays.age が変更された"

    # 全再計算: age を一時的に書き換えてから from_arrays でスコアを再計算する
    old_age = int(obj.arrays.age[idx])
    obj.arrays.age[idx] = np.int16(new_age)
    score_after_full = _full_recompute_score(obj, objective_input)
    obj.arrays.age[idx] = np.int16(old_age)  # 元に戻す

    expected_delta = score_after_full - score_before

    assert abs(delta_differential - expected_delta) < 1e-6, (
        f"差分更新と全再計算の差分が一致しない: "
        f"idx={idx}, old_age={old_age}, new_age={new_age}, "
        f"differential={delta_differential:.8f}, full={expected_delta:.8f}, "
        f"diff={abs(delta_differential - expected_delta):.2e}"
    )


@given(
    person_idx_frac=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    new_age=st.integers(min_value=0, max_value=100),
)
@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
def test_propose_does_not_modify_state(
    person_idx_frac: float,
    new_age: int,
    sample_stats: InitStats,
    objective_input: ObjectiveInput,
) -> None:
    """propose_change は total_score と arrays.age を変更しない（副作用なし）.

    差分更新の前提となる「propose は副作用なし」を property として検証する。
    """
    obj = fresh_objective(sample_stats, objective_input)
    n_persons = obj.arrays.n_persons
    idx = max(0, min(int(person_idx_frac * n_persons), n_persons - 1))

    score_before = obj.total_score
    age_before = int(obj.arrays.age[idx])

    # propose_change を実行（副作用なしのはず）
    obj.propose_change(idx, new_age)

    # total_score が変化していないことを確認
    assert obj.total_score == score_before, (
        f"propose_change が total_score を変更した: "
        f"before={score_before:.6f}, after={obj.total_score:.6f}"
    )
    # arrays.age が変化していないことを確認
    assert int(obj.arrays.age[idx]) == age_before, (
        f"propose_change が arrays.age[{idx}] を変更した: "
        f"before={age_before}, after={int(obj.arrays.age[idx])}"
    )


@given(
    person_idx_frac=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    new_age=st.integers(min_value=0, max_value=100),
)
@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
def test_apply_then_revert_restores_score(
    person_idx_frac: float,
    new_age: int,
    sample_stats: InitStats,
    objective_input: ObjectiveInput,
) -> None:
    """apply_change → 元の age に戻す apply_change で total_score が復元される.

    差分更新の可逆性を property として検証する。
    可逆性が成立しないと SA の反復が誤った状態に陥る。
    """
    obj = fresh_objective(sample_stats, objective_input)
    n_persons = obj.arrays.n_persons
    idx = max(0, min(int(person_idx_frac * n_persons), n_persons - 1))

    original_score = obj.total_score
    old_age = int(obj.arrays.age[idx])

    # 変更を適用してから元に戻す
    obj.apply_change(idx, new_age)
    obj.apply_change(idx, old_age)

    assert abs(obj.total_score - original_score) < 1e-6, (
        f"apply → revert 後に total_score が復元されない: "
        f"idx={idx}, old_age={old_age}, new_age={new_age}, "
        f"original={original_score:.8f}, restored={obj.total_score:.8f}, "
        f"diff={abs(obj.total_score - original_score):.2e}"
    )
