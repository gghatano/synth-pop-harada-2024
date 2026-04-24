"""Tests for domain/registry.py — StringRegistry and typed registries.

TDD Cycle 1: Registry の基本動作（登録 / 参照 / 未登録 KeyError）
"""

from __future__ import annotations

import pytest

from synthpop_jp.domain.registry import SexRegistry, StringRegistry


class TestStringRegistry:
    """StringRegistry の単体テスト."""

    def test_register_returns_int_id(self) -> None:
        """新しい名前を登録すると整数 ID が返る."""
        reg = StringRegistry()
        id_ = reg.register("single")
        assert isinstance(id_, int)

    def test_register_same_name_twice_returns_same_id(self) -> None:
        """同じ名前を 2 回登録しても同じ ID が返る（idempotent）."""
        reg = StringRegistry()
        id1 = reg.register("couple")
        id2 = reg.register("couple")
        assert id1 == id2

    def test_register_different_names_returns_different_ids(self) -> None:
        """異なる名前は異なる ID を持つ."""
        reg = StringRegistry()
        id_a = reg.register("single")
        id_b = reg.register("couple")
        assert id_a != id_b

    def test_id_of_registered_name(self) -> None:
        """登録済み名前を id_of() で引ける."""
        reg = StringRegistry()
        id_ = reg.register("single")
        assert reg.id_of("single") == id_

    def test_id_of_unregistered_name_raises_key_error(self) -> None:
        """未登録名を id_of() すると KeyError."""
        reg = StringRegistry()
        with pytest.raises(KeyError):
            reg.id_of("not_registered")

    def test_name_of_registered_id(self) -> None:
        """登録済み ID を name_of() で引ける."""
        reg = StringRegistry()
        id_ = reg.register("couple_and_children")
        assert reg.name_of(id_) == "couple_and_children"

    def test_name_of_unregistered_id_raises_key_error(self) -> None:
        """未登録 ID を name_of() すると KeyError."""
        reg = StringRegistry()
        with pytest.raises(KeyError):
            reg.name_of(9999)

    def test_ids_are_sequential_from_zero(self) -> None:
        """ID は 0 から連番で割り当てられる."""
        reg = StringRegistry()
        id0 = reg.register("a")
        id1 = reg.register("b")
        id2 = reg.register("c")
        assert (id0, id1, id2) == (0, 1, 2)

    def test_all_names_returns_registered_names(self) -> None:
        """all_names() が登録済み名前の集合を返す."""
        reg = StringRegistry()
        reg.register("single")
        reg.register("couple")
        assert reg.all_names() == {"single", "couple"}

    def test_len_after_registrations(self) -> None:
        """len() が登録済み件数を返す."""
        reg = StringRegistry()
        assert len(reg) == 0
        reg.register("a")
        reg.register("b")
        assert len(reg) == 2


class TestSexRegistry:
    """SexRegistry の単体テスト（M=0, F=1 の固定 ID 保証）."""

    def test_sex_m_is_0(self) -> None:
        """M（男性）の ID は 0."""
        reg = SexRegistry()
        assert reg.id_of("M") == 0

    def test_sex_f_is_1(self) -> None:
        """F（女性）の ID は 1."""
        reg = SexRegistry()
        assert reg.id_of("F") == 1

    def test_sex_name_of_0_is_m(self) -> None:
        """ID=0 の逆引きは M."""
        reg = SexRegistry()
        assert reg.name_of(0) == "M"

    def test_sex_name_of_1_is_f(self) -> None:
        """ID=1 の逆引きは F."""
        reg = SexRegistry()
        assert reg.name_of(1) == "F"
