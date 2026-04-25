"""Property test: save → load で SAState の全フィールドが一致する — Issue #34.

``save_checkpoint`` / ``load_checkpoint`` の round-trip を hypothesis で検証する。
Issue #32 の決定論的テストと重複しないよう、本テストでは hypothesis で
``PopulationArrays`` のサイズ（n_persons）を動的に振る。

なぜ round-trip を検証するか
------------------------------
チェックポイントに誤りがあると SA の resume が正しくない状態から再開し、
再現性（bitwise 一致）が失われる。
hypothesis で n_persons を振ることで、小さいケース・中程度のケースで
pickle/gzip の保存・復元が確実に機能することを保証する。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from synthpop_jp.domain.household import Household
from synthpop_jp.domain.person import Person
from synthpop_jp.domain.registry import FamilyTypeRegistry, RoleRegistry, SexRegistry
from synthpop_jp.optimize.annealing import SAState
from synthpop_jp.optimize.checkpoint import load_checkpoint, save_checkpoint
from synthpop_jp.optimize.objective import ObjectiveState
from synthpop_jp.optimize.state import PopulationArrays

# ---------------------------------------------------------------------------
# テスト用ヘルパー
# ---------------------------------------------------------------------------

ALL_ROLES = ["husband", "wife", "father", "mother", "child", "parent", "single"]
ALL_FAMILY_TYPES = [
    "couple",
    "couple_and_children",
    "single",
    "lone_parent_and_children",
    "couple_and_a_parent",
]


def _make_registries() -> tuple[FamilyTypeRegistry, RoleRegistry, SexRegistry]:
    """テスト用 Registry を返す."""
    family_reg = FamilyTypeRegistry()
    for ft in ALL_FAMILY_TYPES:
        family_reg.register(ft)
    role_reg = RoleRegistry()
    for r in ALL_ROLES:
        role_reg.register(r)
    sex_reg = SexRegistry()
    return family_reg, role_reg, sex_reg


def _make_arrays(n_persons: int, seed: int) -> PopulationArrays:
    """n_persons 人の単身世帯からなる PopulationArrays を生成する.

    seed で age を決定論的に振る。
    """
    rng = np.random.default_rng(seed)
    family_reg, role_reg, sex_reg = _make_registries()
    households = [
        Household(
            household_id=i + 1,
            family_type="single",
            members=[
                Person(
                    household_id=i + 1,
                    role="single",  # type: ignore[arg-type]
                    sex="M" if i % 2 == 0 else "F",  # type: ignore[arg-type]
                    age=int(rng.integers(18, 80)),
                )
            ],
        )
        for i in range(n_persons)
    ]
    return PopulationArrays.from_households(households, family_reg, role_reg, sex_reg)


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


@given(
    n_persons=st.integers(min_value=10, max_value=200),
    seed=st.integers(min_value=0, max_value=2**31 - 1),
)
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
def test_sastate_roundtrip_with_varying_sizes(
    n_persons: int,
    seed: int,
    tmp_path: Path,
) -> None:
    """任意の n_persons で SAState の save/load round-trip が成立する.

    SAState の全フィールド（iter, current_score, best_score, n_accepted, n_total）が
    load 後に bitwise 一致することを検証する。
    """
    rng = np.random.default_rng(seed)
    arrays = _make_arrays(n_persons, seed)
    best_arrays = _make_arrays(n_persons, seed + 1)
    objective = ObjectiveState(arrays=arrays, stats=[], total_score=float(rng.uniform(0, 1000)))

    state = SAState(
        iter=int(rng.integers(0, 10000)),
        current_score=float(rng.uniform(0, 500)),
        best_score=float(rng.uniform(0, 300)),
        n_accepted=int(rng.integers(0, 5000)),
        n_total=int(rng.integers(0, 10000)),
    )
    rng_state = np.random.default_rng(seed + 2).bit_generator.state
    ckpt_path = tmp_path / f"checkpoint_n{n_persons}_s{seed}.pkl.gz"
    save_checkpoint(
        state=state,
        arrays=arrays,
        objective_state=objective,
        best_arrays=best_arrays,
        best_score=state.best_score,
        rng_state=rng_state,
        path=ckpt_path,
    )

    (
        loaded_state,
        _loaded_arrays,
        _loaded_objective,
        _loaded_best_arrays,
        _loaded_best_score,
        _loaded_rng_state,
    ) = load_checkpoint(ckpt_path)

    # SAState の全フィールドが一致する
    assert loaded_state.iter == state.iter, (
        f"iter が一致しない: {loaded_state.iter} != {state.iter}"
    )
    assert abs(loaded_state.current_score - state.current_score) < 1e-9, (
        f"current_score が一致しない: {loaded_state.current_score} != {state.current_score}"
    )
    assert abs(loaded_state.best_score - state.best_score) < 1e-9, (
        f"best_score が一致しない: {loaded_state.best_score} != {state.best_score}"
    )
    assert loaded_state.n_accepted == state.n_accepted, (
        f"n_accepted が一致しない: {loaded_state.n_accepted} != {state.n_accepted}"
    )
    assert loaded_state.n_total == state.n_total, (
        f"n_total が一致しない: {loaded_state.n_total} != {state.n_total}"
    )


@given(
    n_persons=st.integers(min_value=10, max_value=200),
    seed=st.integers(min_value=0, max_value=2**31 - 1),
)
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
def test_population_arrays_roundtrip_with_varying_sizes(
    n_persons: int,
    seed: int,
    tmp_path: Path,
) -> None:
    """任意の n_persons で PopulationArrays の save/load round-trip が成立する.

    age, sex, role, household_id, family_type の全配列が bitwise 一致することを検証する。
    """
    arrays = _make_arrays(n_persons, seed)
    best_arrays = _make_arrays(n_persons, seed + 1)
    objective = ObjectiveState(arrays=arrays, stats=[], total_score=0.0)
    state = SAState()
    rng_state = np.random.default_rng(seed).bit_generator.state
    ckpt_path = tmp_path / f"arrays_n{n_persons}_s{seed}.pkl.gz"
    save_checkpoint(
        state=state,
        arrays=arrays,
        objective_state=objective,
        best_arrays=best_arrays,
        best_score=0.0,
        rng_state=rng_state,
        path=ckpt_path,
    )

    _, loaded_arrays, _, loaded_best_arrays, _, _ = load_checkpoint(ckpt_path)

    # 全配列が bitwise 一致する
    assert np.array_equal(loaded_arrays.age, arrays.age), (
        f"age が一致しない: n_persons={n_persons}, seed={seed}"
    )
    assert np.array_equal(loaded_arrays.sex, arrays.sex), (
        f"sex が一致しない: n_persons={n_persons}, seed={seed}"
    )
    assert np.array_equal(loaded_arrays.role, arrays.role), (
        f"role が一致しない: n_persons={n_persons}, seed={seed}"
    )
    assert np.array_equal(loaded_arrays.household_id, arrays.household_id), (
        f"household_id が一致しない: n_persons={n_persons}, seed={seed}"
    )
    assert np.array_equal(loaded_arrays.family_type, arrays.family_type), (
        f"family_type が一致しない: n_persons={n_persons}, seed={seed}"
    )

    # best_arrays の age も一致する
    assert np.array_equal(loaded_best_arrays.age, best_arrays.age), (
        f"best_arrays.age が一致しない: n_persons={n_persons}, seed={seed}"
    )

    # n_persons が保持される
    assert loaded_arrays.n_persons == n_persons, (
        f"n_persons が一致しない: {loaded_arrays.n_persons} != {n_persons}"
    )


@given(
    n_persons=st.integers(min_value=10, max_value=200),
    seed=st.integers(min_value=0, max_value=2**31 - 1),
)
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
def test_rng_state_roundtrip_with_varying_sizes(
    n_persons: int,
    seed: int,
    tmp_path: Path,
) -> None:
    """任意の n_persons で rng_state の save/load round-trip が成立する.

    rng_state を復元後に生成した乱数が元の rng と bitwise 一致することを検証する。
    SA の resume 時に乱数列が正確に再開できることの保証である。
    """
    rng_orig = np.random.default_rng(seed)
    # 状態を少し進める
    for _ in range(100):
        rng_orig.uniform()

    rng_state_saved = rng_orig.bit_generator.state

    arrays = _make_arrays(n_persons, seed)
    objective = ObjectiveState(arrays=arrays, stats=[], total_score=0.0)
    best_arrays = _make_arrays(n_persons, seed + 1)
    state = SAState(iter=100)
    ckpt_path = tmp_path / f"rng_n{n_persons}_s{seed}.pkl.gz"
    save_checkpoint(
        state=state,
        arrays=arrays,
        objective_state=objective,
        best_arrays=best_arrays,
        best_score=0.0,
        rng_state=rng_state_saved,
        path=ckpt_path,
    )

    _, _, _, _, _, loaded_rng_state = load_checkpoint(ckpt_path)

    # 復元した状態から rng を再構築して次の 10 サンプルを比較
    rng_restored = np.random.default_rng()
    rng_restored.bit_generator.state = loaded_rng_state

    samples_orig = [float(rng_orig.uniform()) for _ in range(10)]
    samples_restored = [float(rng_restored.uniform()) for _ in range(10)]

    for i, (orig, restored) in enumerate(zip(samples_orig, samples_restored, strict=True)):
        assert orig == restored, (
            f"rng sample[{i}] が一致しない: {orig} != {restored}, "
            f"n_persons={n_persons}, seed={seed}"
        )
