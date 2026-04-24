"""Person ドメインモデル.

``Person`` は世帯（``Household``）に属する個人を表す pydantic v2 モデルである。
CSV 入出力と pydantic バリデーションに使用し、SA 内部ループでは使わない。
SA 内部では ``optimize/state.py`` の ``PopulationArrays`` を使う（ADR-0001）。

使い方:

    >>> from synthpop_jp.domain.person import Person
    >>> p = Person(household_id=1, role="husband", sex="M", age=35)
    >>> p.age
    35
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field


class Person(BaseModel):
    """世帯に属する個人を表す pydantic モデル.

    Attributes
    ----------
    household_id : int
        この個人が属する世帯の ID。1 以上の整数。
    role : str
        世帯内での役割。例: ``"husband"``, ``"wife"``, ``"child"``, ``"single"``。
        SA の役割候補は ``domain/registry.py::RoleRegistry`` で管理する。
    sex : Literal["M", "F"]
        性別。``"M"`` = 男性、``"F"`` = 女性。
    age : int
        年齢（歳）。0 以上 120 以下。
    """

    household_id: Annotated[int, Field(ge=1)]
    role: str
    sex: Literal["M", "F"]
    age: Annotated[int, Field(ge=0, le=120)]
