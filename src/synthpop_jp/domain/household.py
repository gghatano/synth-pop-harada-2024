"""Household ドメインモデル.

``Household`` は世帯を表す pydantic v2 モデルである。
CSV 入出力と pydantic バリデーションに使用し、SA 内部ループでは使わない。
SA 内部では ``optimize/state.py`` の ``PopulationArrays`` を使う（ADR-0001）。

``PopulationArrays.from_households(households)`` で並列配列に変換し、
``PopulationArrays.to_households()`` で逆変換できる。

使い方:

    >>> from synthpop_jp.domain.household import Household
    >>> from synthpop_jp.domain.person import Person
    >>> person = Person(household_id=1, role="single", sex="F", age=45)
    >>> hh = Household(household_id=1, family_type="single", members=[person])
    >>> hh.household_id
    1
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field

from synthpop_jp.domain.person import Person


class Household(BaseModel):
    """世帯を表す pydantic モデル.

    Attributes
    ----------
    household_id : int
        世帯の一意な識別子。1 以上の整数。
    family_type : str
        家族類型。例: ``"single"``, ``"couple"``, ``"couple_and_children"``。
        SA の家族類型候補は ``domain/registry.py::FamilyTypeRegistry`` で管理する。
    members : list[Person]
        世帯員のリスト。1 人以上必須。
    """

    household_id: Annotated[int, Field(ge=1)]
    family_type: str
    members: Annotated[list[Person], Field(min_length=1)]
