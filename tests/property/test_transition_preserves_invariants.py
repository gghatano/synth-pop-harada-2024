"""Property test: age-change 遷移後も household size・family_type 分布が不変 — Issue #34.

``AgeChangeTransition`` が変えるのは age だけであり、
世帯の構成（household_id / role / sex / family_type）は変わらない。
この不変性を hypothesis で網羅的に検証する。

なぜ不変性が重要か
-------------------
遷移が誤って household_id や role を変えると、次の差分更新計算が狂う。
「age しか変えない」という前提は SA の正確性の基盤である。
"""

from __future__ import annotations

from collections import Counter

import numpy as np
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from synthpop_jp.optimize.state import PopulationArrays
from synthpop_jp.optimize.transitions import AgeChangeTransition
from synthpop_jp.rng import SeedRegistry

from .conftest import InitStats, ObjectiveInput, fresh_arrays

# ---------------------------------------------------------------------------
# 不変量の計算ヘルパー
# ---------------------------------------------------------------------------


def compute_household_sizes(arrays: PopulationArrays) -> Counter[int]:
    """世帯 ID ごとのメンバー数を返す."""
    return Counter(int(hid) for hid in arrays.household_id)


def compute_family_type_dist(arrays: PopulationArrays) -> Counter[int]:
    """family_type の分布（各世帯の family_type を 1 票とみなす）を返す.

    各世帯の代表メンバー（先頭インデックス）の family_type を集計する。
    """
    seen_hids: set[int] = set()
    dist: Counter[int] = Counter()
    for i in range(arrays.n_persons):
        hid = int(arrays.household_id[i])
        if hid not in seen_hids:
            seen_hids.add(hid)
            dist[int(arrays.family_type[i])] += 1
    return dist


def compute_role_dist(arrays: PopulationArrays) -> Counter[int]:
    """role の分布を返す（全 person の role カウント）."""
    return Counter(int(r) for r in arrays.role)


def compute_sex_dist(arrays: PopulationArrays) -> Counter[int]:
    """sex の分布を返す（全 person の sex カウント）."""
    return Counter(int(s) for s in arrays.sex)


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


@given(
    n_iters=st.integers(min_value=1, max_value=100),
    seed=st.integers(min_value=0, max_value=2**31 - 1),
)
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
def test_age_change_preserves_household_sizes(
    n_iters: int,
    seed: int,
    sample_stats: InitStats,
    objective_input: ObjectiveInput,
) -> None:
    """age-change 遷移を n_iters 回繰り返しても household size 分布が不変.

    AgeChangeTransition.propose() は (person_idx, new_age) を返すだけであり、
    呼び出し元が age を更新する。そのため household_id は変化しないはずである。
    """
    arrays = fresh_arrays(sample_stats)
    demo_rows = objective_input.demographic_by_age_sex

    initial_household_sizes = compute_household_sizes(arrays)

    rng = SeedRegistry(root=seed).rng("test_transition")
    transition = AgeChangeTransition(
        arrays=arrays,
        demo_by_age_sex=demo_rows,
        rng=rng,
    )

    for _ in range(n_iters):
        try:
            idx, new_age = transition.propose()
        except Exception:
            # TransitionError など — スキップして次へ
            continue
        # age だけを更新する（ObjectiveState 経由ではなく直接更新）
        arrays.age[idx] = np.int16(new_age)

    after_household_sizes = compute_household_sizes(arrays)

    assert initial_household_sizes == after_household_sizes, (
        f"household size 分布が変化した: "
        f"before={dict(initial_household_sizes)}, "
        f"after={dict(after_household_sizes)}"
    )


@given(
    n_iters=st.integers(min_value=1, max_value=100),
    seed=st.integers(min_value=0, max_value=2**31 - 1),
)
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
def test_age_change_preserves_family_type_distribution(
    n_iters: int,
    seed: int,
    sample_stats: InitStats,
    objective_input: ObjectiveInput,
) -> None:
    """age-change 遷移を n_iters 回繰り返しても family_type 分布が不変.

    family_type は age-change では変更されないため、分布は常に一定のはずである。
    """
    arrays = fresh_arrays(sample_stats)
    demo_rows = objective_input.demographic_by_age_sex

    initial_family_dist = compute_family_type_dist(arrays)

    rng = SeedRegistry(root=seed).rng("test_transition")
    transition = AgeChangeTransition(
        arrays=arrays,
        demo_by_age_sex=demo_rows,
        rng=rng,
    )

    for _ in range(n_iters):
        try:
            idx, new_age = transition.propose()
        except Exception:
            continue
        arrays.age[idx] = np.int16(new_age)

    after_family_dist = compute_family_type_dist(arrays)

    assert initial_family_dist == after_family_dist, (
        f"family_type 分布が変化した: "
        f"before={dict(initial_family_dist)}, "
        f"after={dict(after_family_dist)}"
    )


@given(
    n_iters=st.integers(min_value=1, max_value=100),
    seed=st.integers(min_value=0, max_value=2**31 - 1),
)
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
def test_age_change_preserves_role_distribution(
    n_iters: int,
    seed: int,
    sample_stats: InitStats,
    objective_input: ObjectiveInput,
) -> None:
    """age-change 遷移を n_iters 回繰り返しても role 分布が不変.

    AgeChangeTransition は age のみを変更するため、role は不変のはずである。
    """
    arrays = fresh_arrays(sample_stats)
    demo_rows = objective_input.demographic_by_age_sex

    initial_role_dist = compute_role_dist(arrays)

    rng = SeedRegistry(root=seed).rng("test_transition")
    transition = AgeChangeTransition(
        arrays=arrays,
        demo_by_age_sex=demo_rows,
        rng=rng,
    )

    for _ in range(n_iters):
        try:
            idx, new_age = transition.propose()
        except Exception:
            continue
        arrays.age[idx] = np.int16(new_age)

    after_role_dist = compute_role_dist(arrays)

    assert initial_role_dist == after_role_dist, (
        f"role 分布が変化した: before={dict(initial_role_dist)}, after={dict(after_role_dist)}"
    )


@given(
    n_iters=st.integers(min_value=1, max_value=100),
    seed=st.integers(min_value=0, max_value=2**31 - 1),
)
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
def test_age_change_preserves_sex_distribution(
    n_iters: int,
    seed: int,
    sample_stats: InitStats,
    objective_input: ObjectiveInput,
) -> None:
    """age-change 遷移を n_iters 回繰り返しても sex 分布が不変.

    AgeChangeTransition は age のみを変更するため、sex は不変のはずである。
    """
    arrays = fresh_arrays(sample_stats)
    demo_rows = objective_input.demographic_by_age_sex

    initial_sex_dist = compute_sex_dist(arrays)

    rng = SeedRegistry(root=seed).rng("test_transition")
    transition = AgeChangeTransition(
        arrays=arrays,
        demo_by_age_sex=demo_rows,
        rng=rng,
    )

    for _ in range(n_iters):
        try:
            idx, new_age = transition.propose()
        except Exception:
            continue
        arrays.age[idx] = np.int16(new_age)

    after_sex_dist = compute_sex_dist(arrays)

    assert initial_sex_dist == after_sex_dist, (
        f"sex 分布が変化した: before={dict(initial_sex_dist)}, after={dict(after_sex_dist)}"
    )
