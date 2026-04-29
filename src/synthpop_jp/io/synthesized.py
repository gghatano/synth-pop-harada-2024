"""Reader for ``synthetic_persons.csv`` to reconstruct PopulationArrays — Issue #59.

``generate`` の出力 CSV から ``PopulationArrays`` を再構築する関数を提供する。
``synthpop-jp evaluate`` が合成人口の品質を評価するときに使う（generate を再実行
せず、ファイルから読み戻す）。

提供するもの
------------
- ``reconstruct_population_arrays_from_persons_csv(persons_csv)``
  → :class:`~synthpop_jp.optimize.state.PopulationArrays`
"""

from __future__ import annotations

import csv
from typing import TYPE_CHECKING, cast

from synthpop_jp.domain.household import Household
from synthpop_jp.domain.person import Person
from synthpop_jp.domain.registry import FamilyTypeRegistry, RoleRegistry, SexRegistry
from synthpop_jp.optimize.state import PopulationArrays

if TYPE_CHECKING:
    from pathlib import Path


_HH_ID_PREFIX = "HH_"


def reconstruct_population_arrays_from_persons_csv(
    persons_csv: Path,
) -> PopulationArrays:
    """``synthetic_persons.csv`` から ``PopulationArrays`` を再構築する.

    ``generate`` が書き出した CSV の各行を 1 person として解釈し、
    ``household_id`` でグルーピングして ``Household`` のリストに戻し、
    ``PopulationArrays.from_households`` で並列配列化する。

    必要な CSV 列: ``household_id`` (``"HH_NNNNNN"`` 形式)、``family_type``、
    ``role``、``sex`` (``"M"`` / ``"F"``)、``age``。

    Parameters
    ----------
    persons_csv : Path
        ``synthetic_persons.csv`` のパス。

    Returns
    -------
    PopulationArrays
        再構築された人口配列。Registry は CSV 内の登場順で登録される。

    Raises
    ------
    FileNotFoundError
        指定された CSV が存在しない場合。
    """
    family_reg = FamilyTypeRegistry()
    role_reg = RoleRegistry()
    sex_reg = SexRegistry()

    households_dict: dict[int, dict[str, object]] = {}
    seen_family_types: set[str] = set()
    seen_roles: set[str] = set()

    with persons_csv.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            hh_id_str = row["household_id"]
            hh_id = int(str(hh_id_str).removeprefix(_HH_ID_PREFIX))
            family_type = row["family_type"]
            role = row["role"]
            sex = row["sex"]
            age = int(row["age"])

            # 登場した family_type / role を Registry に登録
            if family_type not in seen_family_types:
                family_reg.register(family_type)
                seen_family_types.add(family_type)
            if role not in seen_roles:
                role_reg.register(role)
                seen_roles.add(role)

            if hh_id not in households_dict:
                households_dict[hh_id] = {"family_type": family_type, "members": []}
            members = cast("list[Person]", households_dict[hh_id]["members"])
            members.append(Person(household_id=hh_id, role=role, sex=sex, age=age))  # type: ignore[arg-type]

    households = [
        Household(
            household_id=hid,
            family_type=cast("str", info["family_type"]),
            members=cast("list[Person]", info["members"]),
        )
        for hid, info in sorted(households_dict.items())
    ]
    return PopulationArrays.from_households(households, family_reg, role_reg, sex_reg)
