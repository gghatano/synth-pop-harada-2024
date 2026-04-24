"""Tests for domain/household.py and domain/person.py — pydantic モデルの検証.

TDD Cycle 2: Person / Household モデルの基本バリデーション
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from synthpop_jp.domain.household import Household
from synthpop_jp.domain.person import Person


class TestPerson:
    """Person pydantic モデルの単体テスト."""

    def test_valid_person(self) -> None:
        """有効な Person が構築できる."""
        p = Person(household_id=1, role="husband", sex="M", age=35)
        assert p.household_id == 1
        assert p.role == "husband"
        assert p.sex == "M"
        assert p.age == 35

    def test_sex_must_be_m_or_f(self) -> None:
        """sex は M か F のみ受け付ける."""
        with pytest.raises(ValidationError):
            Person(household_id=1, role="wife", sex="X", age=30)  # type: ignore[arg-type]

    def test_age_cannot_be_negative(self) -> None:
        """年齢は 0 以上でなければならない."""
        with pytest.raises(ValidationError):
            Person(household_id=1, role="child", sex="F", age=-1)

    def test_age_cannot_exceed_120(self) -> None:
        """年齢は 120 以下でなければならない."""
        with pytest.raises(ValidationError):
            Person(household_id=1, role="husband", sex="M", age=121)

    def test_age_zero_is_valid(self) -> None:
        """年齢 0（生後）は有効."""
        p = Person(household_id=1, role="child", sex="M", age=0)
        assert p.age == 0

    def test_age_120_is_valid(self) -> None:
        """年齢 120 は有効."""
        p = Person(household_id=1, role="husband", sex="M", age=120)
        assert p.age == 120


class TestHousehold:
    """Household pydantic モデルの単体テスト."""

    def test_valid_single_household(self) -> None:
        """single 世帯（単身）が構築できる."""
        person = Person(household_id=1, role="single", sex="F", age=45)
        hh = Household(household_id=1, family_type="single", members=[person])
        assert hh.household_id == 1
        assert hh.family_type == "single"
        assert len(hh.members) == 1

    def test_valid_couple_household(self) -> None:
        """couple 世帯（夫婦のみ）が構築できる."""
        husband = Person(household_id=2, role="husband", sex="M", age=40)
        wife = Person(household_id=2, role="wife", sex="F", age=38)
        hh = Household(household_id=2, family_type="couple", members=[husband, wife])
        assert len(hh.members) == 2

    def test_household_must_have_at_least_one_member(self) -> None:
        """世帯員が 0 人の世帯は拒否する."""
        with pytest.raises(ValidationError):
            Household(household_id=3, family_type="single", members=[])

    def test_household_id_must_be_positive(self) -> None:
        """household_id は 1 以上でなければならない（0 は拒否）."""
        person = Person(household_id=1, role="single", sex="M", age=30)
        with pytest.raises(ValidationError):
            Household(household_id=0, family_type="single", members=[person])
