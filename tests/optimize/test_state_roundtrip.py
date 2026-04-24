"""Tests for PopulationArrays — dtype・from_households・to_households・メモリ効率.

TDD Cycle 3: dtype 設計と空配列生成
TDD Cycle 4: from_households (1 世帯からの変換)
TDD Cycle 5: to_households (1 世帯への逆変換)
TDD Cycle 6: hypothesis 往復 property test
TDD Cycle 7: メモリ効率測定テスト
"""

from __future__ import annotations

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from synthpop_jp.domain.household import Household
from synthpop_jp.domain.person import Person
from synthpop_jp.domain.registry import FamilyTypeRegistry, RoleRegistry, SexRegistry
from synthpop_jp.optimize.state import PopulationArrays

# ---------------------------------------------------------------------------
# ヘルパー: テスト用 Registry の生成
# ---------------------------------------------------------------------------


def make_registries() -> tuple[FamilyTypeRegistry, RoleRegistry, SexRegistry]:
    """テスト用の登録済み Registry を返す."""
    family_reg = FamilyTypeRegistry()
    family_reg.register("single")
    family_reg.register("couple")
    family_reg.register("couple_and_children")

    role_reg = RoleRegistry()
    role_reg.register("single")
    role_reg.register("husband")
    role_reg.register("wife")
    role_reg.register("child")

    sex_reg = SexRegistry()  # M=0, F=1 固定

    return family_reg, role_reg, sex_reg


# ---------------------------------------------------------------------------
# Cycle 3: dtype 設計と空配列生成
# ---------------------------------------------------------------------------


class TestPopulationArraysDtype:
    """PopulationArrays の dtype が ADR-0001 の仕様に従うことを確認."""

    def test_age_dtype_is_int16(self) -> None:
        """age 配列の dtype は int16."""
        family_reg, role_reg, sex_reg = make_registries()
        arrays = PopulationArrays.empty(family_reg, role_reg, sex_reg)
        assert arrays.age.dtype == np.int16

    def test_sex_dtype_is_int8(self) -> None:
        """sex 配列の dtype は int8."""
        family_reg, role_reg, sex_reg = make_registries()
        arrays = PopulationArrays.empty(family_reg, role_reg, sex_reg)
        assert arrays.sex.dtype == np.int8

    def test_role_dtype_is_int8(self) -> None:
        """role 配列の dtype は int8."""
        family_reg, role_reg, sex_reg = make_registries()
        arrays = PopulationArrays.empty(family_reg, role_reg, sex_reg)
        assert arrays.role.dtype == np.int8

    def test_household_id_dtype_is_int32(self) -> None:
        """household_id 配列の dtype は int32."""
        family_reg, role_reg, sex_reg = make_registries()
        arrays = PopulationArrays.empty(family_reg, role_reg, sex_reg)
        assert arrays.household_id.dtype == np.int32

    def test_family_type_dtype_is_int8(self) -> None:
        """family_type 配列の dtype は int8（person-broadcast）."""
        family_reg, role_reg, sex_reg = make_registries()
        arrays = PopulationArrays.empty(family_reg, role_reg, sex_reg)
        assert arrays.family_type.dtype == np.int8

    def test_empty_arrays_have_zero_persons(self) -> None:
        """empty() は n_persons=0 の配列を返す."""
        family_reg, role_reg, sex_reg = make_registries()
        arrays = PopulationArrays.empty(family_reg, role_reg, sex_reg)
        assert arrays.age.shape == (0,)
        assert arrays.sex.shape == (0,)
        assert arrays.role.shape == (0,)
        assert arrays.household_id.shape == (0,)
        assert arrays.family_type.shape == (0,)

    def test_n_persons_property(self) -> None:
        """n_persons プロパティが person 数を返す."""
        family_reg, role_reg, sex_reg = make_registries()
        arrays = PopulationArrays.empty(family_reg, role_reg, sex_reg)
        assert arrays.n_persons == 0


# ---------------------------------------------------------------------------
# Cycle 4: from_households (1 世帯から変換)
# ---------------------------------------------------------------------------


class TestFromHouseholds:
    """PopulationArrays.from_households の単体テスト."""

    def test_single_person_household(self) -> None:
        """単身世帯 1 つから配列が生成できる."""
        family_reg, role_reg, sex_reg = make_registries()
        person = Person(household_id=1, role="single", sex="F", age=45)
        hh = Household(household_id=1, family_type="single", members=[person])
        arrays = PopulationArrays.from_households([hh], family_reg, role_reg, sex_reg)
        assert arrays.n_persons == 1

    def test_age_is_correctly_encoded(self) -> None:
        """年齢が int16 で正しく記録される."""
        family_reg, role_reg, sex_reg = make_registries()
        person = Person(household_id=1, role="single", sex="F", age=45)
        hh = Household(household_id=1, family_type="single", members=[person])
        arrays = PopulationArrays.from_households([hh], family_reg, role_reg, sex_reg)
        assert arrays.age[0] == 45

    def test_sex_m_encoded_as_0(self) -> None:
        """sex=M は 0 に変換される."""
        family_reg, role_reg, sex_reg = make_registries()
        person = Person(household_id=1, role="husband", sex="M", age=40)
        hh = Household(household_id=1, family_type="couple", members=[person])
        arrays = PopulationArrays.from_households([hh], family_reg, role_reg, sex_reg)
        assert arrays.sex[0] == 0

    def test_sex_f_encoded_as_1(self) -> None:
        """sex=F は 1 に変換される."""
        family_reg, role_reg, sex_reg = make_registries()
        person = Person(household_id=1, role="wife", sex="F", age=38)
        hh = Household(household_id=1, family_type="couple", members=[person])
        arrays = PopulationArrays.from_households([hh], family_reg, role_reg, sex_reg)
        assert arrays.sex[0] == 1

    def test_household_id_is_correctly_encoded(self) -> None:
        """household_id が int32 で正しく記録される."""
        family_reg, role_reg, sex_reg = make_registries()
        person = Person(household_id=5, role="single", sex="M", age=30)
        hh = Household(household_id=5, family_type="single", members=[person])
        arrays = PopulationArrays.from_households([hh], family_reg, role_reg, sex_reg)
        assert arrays.household_id[0] == 5

    def test_family_type_is_broadcast_to_all_members(self) -> None:
        """family_type が世帯の全メンバーに broadcast される."""
        family_reg, role_reg, sex_reg = make_registries()
        husband = Person(household_id=1, role="husband", sex="M", age=40)
        wife = Person(household_id=1, role="wife", sex="F", age=38)
        hh = Household(household_id=1, family_type="couple", members=[husband, wife])
        arrays = PopulationArrays.from_households([hh], family_reg, role_reg, sex_reg)
        couple_id = family_reg.id_of("couple")
        assert arrays.family_type[0] == couple_id
        assert arrays.family_type[1] == couple_id

    def test_two_households(self) -> None:
        """2 世帯分が連結される."""
        family_reg, role_reg, sex_reg = make_registries()
        p1 = Person(household_id=1, role="single", sex="M", age=30)
        hh1 = Household(household_id=1, family_type="single", members=[p1])
        p2 = Person(household_id=2, role="single", sex="F", age=25)
        hh2 = Household(household_id=2, family_type="single", members=[p2])
        arrays = PopulationArrays.from_households([hh1, hh2], family_reg, role_reg, sex_reg)
        assert arrays.n_persons == 2

    def test_empty_household_list(self) -> None:
        """世帯リストが空のとき n_persons=0."""
        family_reg, role_reg, sex_reg = make_registries()
        arrays = PopulationArrays.from_households([], family_reg, role_reg, sex_reg)
        assert arrays.n_persons == 0


# ---------------------------------------------------------------------------
# Cycle 5: to_households (逆変換)
# ---------------------------------------------------------------------------


class TestToHouseholds:
    """PopulationArrays.to_households の単体テスト."""

    def test_roundtrip_single_person(self) -> None:
        """単身世帯 1 つの往復変換が一致する."""
        family_reg, role_reg, sex_reg = make_registries()
        person = Person(household_id=1, role="single", sex="F", age=45)
        hh = Household(household_id=1, family_type="single", members=[person])
        arrays = PopulationArrays.from_households([hh], family_reg, role_reg, sex_reg)
        recovered = arrays.to_households()
        assert len(recovered) == 1
        assert recovered[0].household_id == 1
        assert recovered[0].family_type == "single"
        assert len(recovered[0].members) == 1
        m = recovered[0].members[0]
        assert m.sex == "F"
        assert m.age == 45
        assert m.role == "single"

    def test_roundtrip_couple_household(self) -> None:
        """夫婦世帯の往復変換が一致する."""
        family_reg, role_reg, sex_reg = make_registries()
        husband = Person(household_id=2, role="husband", sex="M", age=40)
        wife = Person(household_id=2, role="wife", sex="F", age=38)
        hh = Household(household_id=2, family_type="couple", members=[husband, wife])
        arrays = PopulationArrays.from_households([hh], family_reg, role_reg, sex_reg)
        recovered = arrays.to_households()
        assert len(recovered) == 1
        assert recovered[0].household_id == 2
        # メンバー数が正しい
        assert len(recovered[0].members) == 2

    def test_roundtrip_empty(self) -> None:
        """空リストの往復は空リストを返す."""
        family_reg, role_reg, sex_reg = make_registries()
        arrays = PopulationArrays.from_households([], family_reg, role_reg, sex_reg)
        recovered = arrays.to_households()
        assert recovered == []


# ---------------------------------------------------------------------------
# Cycle 6: hypothesis 往復 property test
# ---------------------------------------------------------------------------

FAMILY_TYPES = ["single", "couple", "couple_and_children"]
ROLES = ["single", "husband", "wife", "child"]
SEXES = ["M", "F"]


def person_strategy(household_id: int) -> st.SearchStrategy[Person]:
    """hypothesis で Person を生成するストラテジー."""
    return st.builds(
        Person,
        household_id=st.just(household_id),
        role=st.sampled_from(ROLES),
        sex=st.sampled_from(SEXES),
        age=st.integers(min_value=0, max_value=120),
    )


def household_strategy() -> st.SearchStrategy[Household]:
    """hypothesis で Household を生成するストラテジー."""
    household_id = st.integers(min_value=1, max_value=10000)
    return household_id.flatmap(
        lambda hid: st.builds(
            Household,
            household_id=st.just(hid),
            family_type=st.sampled_from(FAMILY_TYPES),
            members=st.lists(person_strategy(hid), min_size=1, max_size=6),
        )
    )


def unique_household_list_strategy() -> st.SearchStrategy[list[Household]]:
    """重複しない household_id を持つ Household リストのストラテジー.

    hypothesis が同一 household_id を持つ世帯を生成すると
    from_households → to_households の往復で世帯数が変わるため、
    household_id の一意性を保証する。
    """
    return st.lists(
        st.integers(min_value=1, max_value=10000),
        min_size=0,
        max_size=50,
        unique=True,
    ).flatmap(
        lambda ids: st.fixed_dictionaries(
            {
                hid: st.builds(
                    Household,
                    household_id=st.just(hid),
                    family_type=st.sampled_from(FAMILY_TYPES),
                    members=st.lists(person_strategy(hid), min_size=1, max_size=6),
                )
                for hid in ids
            }
        ).map(lambda d: list(d.values()))
    )


@given(households=unique_household_list_strategy())
@settings(max_examples=200)
def test_from_households_to_households_roundtrip(households: list[Household]) -> None:
    """任意の Household リストが arrays 往復で元のデータと一致する (hypothesis).

    往復後に同じ household_id・family_type・メンバーの sex/age/role が保存されることを確認。
    household_id は一意性を保証したリストで生成する。
    """
    family_reg = FamilyTypeRegistry()
    for ft in FAMILY_TYPES:
        family_reg.register(ft)
    role_reg = RoleRegistry()
    for r in ROLES:
        role_reg.register(r)
    sex_reg = SexRegistry()

    arrays = PopulationArrays.from_households(households, family_reg, role_reg, sex_reg)
    recovered = arrays.to_households()

    # 世帯数が一致
    assert len(recovered) == len(households)

    # 世帯ごとの内容が一致（household_id でソートして比較）
    original_by_id = {hh.household_id: hh for hh in households}
    recovered_by_id = {hh.household_id: hh for hh in recovered}

    for hid, orig in original_by_id.items():
        rec = recovered_by_id[hid]
        assert rec.family_type == orig.family_type
        assert len(rec.members) == len(orig.members)

        orig_members = sorted(orig.members, key=lambda p: (p.age, p.sex, p.role))
        rec_members = sorted(rec.members, key=lambda p: (p.age, p.sex, p.role))
        for op, rp in zip(orig_members, rec_members, strict=True):
            assert rp.age == op.age
            assert rp.sex == op.sex
            assert rp.role == op.role


# ---------------------------------------------------------------------------
# Cycle 7: メモリ効率測定テスト
# ---------------------------------------------------------------------------


def test_memory_efficiency_10000_households() -> None:
    """10,000 世帯（3 人/世帯 = 30,000 人）で 1 人あたり ≤ 64 bytes.

    測定方法:
    - 全配列の nbytes を合計
    - Registry の Python オブジェクトはオーバーヘッドに含めない（SA 実行中は 1 回のみ生成）
    - 30,000 人 × 64 bytes = 1,920,000 bytes = 約 1.83 MiB が上限
    """
    family_reg = FamilyTypeRegistry()
    for ft in FAMILY_TYPES:
        family_reg.register(ft)
    role_reg = RoleRegistry()
    for r in ROLES:
        role_reg.register(r)
    sex_reg = SexRegistry()

    n_households = 10_000
    members_per_hh = 3
    n_persons = n_households * members_per_hh

    households: list[Household] = []
    for i in range(n_households):
        hid = i + 1
        members = [
            Person(household_id=hid, role="husband", sex="M", age=40),
            Person(household_id=hid, role="wife", sex="F", age=38),
            Person(household_id=hid, role="child", sex="M", age=10),
        ]
        households.append(
            Household(household_id=hid, family_type="couple_and_children", members=members)
        )

    arrays = PopulationArrays.from_households(households, family_reg, role_reg, sex_reg)

    total_bytes = (
        arrays.age.nbytes
        + arrays.sex.nbytes
        + arrays.role.nbytes
        + arrays.household_id.nbytes
        + arrays.family_type.nbytes
    )

    bytes_per_person = total_bytes / n_persons
    assert bytes_per_person <= 64, (
        f"1 人あたり {bytes_per_person:.1f} bytes は 64 bytes の上限を超えた"
    )


def test_apply_change_docstring_is_documented() -> None:
    """apply_change に関する差分更新スニペットが docstring に存在する."""
    # ADR-0001 が要求する差分更新 API のドキュメントを確認
    doc = PopulationArrays.__doc__ or ""
    assert "apply_change" in doc, (
        "PopulationArrays の docstring に apply_change スニペットが見当たらない"
    )
