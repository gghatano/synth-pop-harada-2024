"""SA state containers.

The :class:`PopulationArrays` dataclass is the internal parallel-array
representation used by the Simulated Annealing inner loop (see
``docs/reviews/review-python.md`` 指摘1 and ADR-0001). The boundary with
the pydantic domain models lives in :mod:`synthpop_jp.domain`.

差分更新 (apply_change) のスニペット例
---------------------------------------
SA の 1 遷移で個人 ``idx`` の年齢を ``new_age`` に更新するには:

.. code-block:: python

    def apply_change(arrays: PopulationArrays, idx: int, new_age: int) -> None:
        \"\"\"O(1) の差分更新: 個人 idx の age を new_age に書き換える.

        この関数は SA の ``Transition.apply`` から呼ばれる。
        元の値は ``Proposal.before`` に退避済みのため、``Transition.revert``
        で ``arrays.age[idx] = proposal.before[0]`` として元に戻せる。
        \"\"\"
        arrays.age[idx] = np.int16(new_age)

``compute_delta_objective`` と連携する場合は、変更前後の配列要素を
``Proposal.before`` / ``Proposal.after`` に記録し、
``ObjectiveState.propose / apply / revert`` で差分スコアを更新する
（Phase 2 で実装する ``optimize/objective.py`` を参照）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from synthpop_jp.domain.household import Household
    from synthpop_jp.domain.registry import (
        FamilyTypeRegistry,
        RoleRegistry,
        SexRegistry,
    )


@dataclass
class PopulationArrays:
    """NumPy 並列配列で人口全体を表す SA 内部表現（ADR-0001 準拠）.

    各配列は person index を共有する。すなわち、同じ添字 ``i`` が
    1 人の個人の全属性に対応する（Structure of Arrays 方式）。

    Attributes
    ----------
    age : np.ndarray
        ``int16`` 配列、shape=(n_persons,)。年齢（歳）。
    sex : np.ndarray
        ``int8`` 配列。``0`` = 男性（M）、``1`` = 女性（F）。
    role : np.ndarray
        ``int8`` 配列。世帯内の役割を整数 ID で表す。
        対応する文字列は :class:`~synthpop_jp.domain.registry.RoleRegistry` で引く。
    household_id : np.ndarray
        ``int32`` 配列。各 person が属する世帯の ID。
    family_type : np.ndarray
        ``int8`` 配列。世帯の家族類型を person に broadcast した値。
        対応する文字列は
        :class:`~synthpop_jp.domain.registry.FamilyTypeRegistry` で引く。

    References
    ----------
    ADR-0001 の差分更新前提:

    .. code-block:: python

        def apply_change(arrays: PopulationArrays, idx: int, new_age: int) -> None:
            \"\"\"O(1) の差分更新: 個人 idx の age を new_age に書き換える.\"\"\"
            arrays.age[idx] = np.int16(new_age)

    元の値は ``Proposal.before`` に退避し、revert 時に復元する。
    差分目的関数（``compute_delta_objective``）との連携は Phase 2 で実装する。

    Notes
    -----
    I/O 境界（CSV → pydantic → 並列配列）は
    :meth:`from_households` と :meth:`to_households` が担う。
    SA 内部ループでは pydantic モデルへの変換を行わない。

    メモリ見積もり（dtype 合計）:

    - age:          int16 = 2 bytes/person
    - sex:          int8  = 1 byte/person
    - role:         int8  = 1 byte/person
    - household_id: int32 = 4 bytes/person
    - family_type:  int8  = 1 byte/person
    - 合計:          9 bytes/person → 1 人あたり ≤ 64 bytes を大きく下回る
    """

    age: np.ndarray[Any, Any]
    sex: np.ndarray[Any, Any]
    role: np.ndarray[Any, Any]
    household_id: np.ndarray[Any, Any]
    family_type: np.ndarray[Any, Any]
    _family_reg: FamilyTypeRegistry
    _role_reg: RoleRegistry
    _sex_reg: SexRegistry

    @property
    def n_persons(self) -> int:
        """配列が保持する person 数を返す."""
        return int(self.age.shape[0])

    @property
    def role_reg(self) -> RoleRegistry:
        """役割 ↔ 整数 ID の Registry を返す."""
        return self._role_reg

    @property
    def family_reg(self) -> FamilyTypeRegistry:
        """家族類型 ↔ 整数 ID の Registry を返す."""
        return self._family_reg

    @property
    def sex_reg(self) -> SexRegistry:
        """性別 ↔ 整数 ID の Registry を返す."""
        return self._sex_reg

    @classmethod
    def empty(
        cls,
        family_reg: FamilyTypeRegistry,
        role_reg: RoleRegistry,
        sex_reg: SexRegistry,
    ) -> PopulationArrays:
        """Person が 0 人の空の :class:`PopulationArrays` を生成する.

        Parameters
        ----------
        family_reg : FamilyTypeRegistry
            家族類型 ↔ 整数 ID の Registry。
        role_reg : RoleRegistry
            役割 ↔ 整数 ID の Registry。
        sex_reg : SexRegistry
            性別 ↔ 整数 ID の Registry。

        Returns
        -------
        PopulationArrays
            shape=(0,) の空配列を持つ :class:`PopulationArrays`。
        """
        return cls(
            age=np.empty(0, dtype=np.int16),
            sex=np.empty(0, dtype=np.int8),
            role=np.empty(0, dtype=np.int8),
            household_id=np.empty(0, dtype=np.int32),
            family_type=np.empty(0, dtype=np.int8),
            _family_reg=family_reg,
            _role_reg=role_reg,
            _sex_reg=sex_reg,
        )

    @classmethod
    def from_households(
        cls,
        households: list[Household],
        family_reg: FamilyTypeRegistry,
        role_reg: RoleRegistry,
        sex_reg: SexRegistry,
    ) -> PopulationArrays:
        """Pydantic :class:`~synthpop_jp.domain.household.Household` のリストから生成する.

        各 Household の members を走査して並列配列に変換する。
        変換は I/O 境界で 1 回だけ行う。SA 内部では呼び出さない。

        Parameters
        ----------
        households : list[Household]
            変換元の世帯リスト。空リストも受け付ける。
        family_reg : FamilyTypeRegistry
            家族類型 ↔ 整数 ID の Registry。family_type の文字列を整数に変換する。
        role_reg : RoleRegistry
            役割 ↔ 整数 ID の Registry。role の文字列を整数に変換する。
        sex_reg : SexRegistry
            性別 ↔ 整数 ID の Registry（M=0, F=1 固定）。

        Returns
        -------
        PopulationArrays
            全 households の members を person index で連結した配列。

        Examples
        --------
        >>> from synthpop_jp.domain.household import Household
        >>> from synthpop_jp.domain.person import Person
        >>> from synthpop_jp.domain.registry import FamilyTypeRegistry, RoleRegistry, SexRegistry
        >>> family_reg = FamilyTypeRegistry()
        >>> _ = family_reg.register("single")
        >>> role_reg = RoleRegistry()
        >>> _ = role_reg.register("single")
        >>> sex_reg = SexRegistry()
        >>> person = Person(household_id=1, role="single", sex="F", age=45)
        >>> hh = Household(household_id=1, family_type="single", members=[person])
        >>> arrays = PopulationArrays.from_households([hh], family_reg, role_reg, sex_reg)
        >>> arrays.n_persons
        1
        >>> arrays.age[0]
        45
        """
        if not households:
            return cls.empty(family_reg, role_reg, sex_reg)

        # 全 person 数を先に計算して配列を一括確保
        n_persons = sum(len(hh.members) for hh in households)

        age_arr = np.empty(n_persons, dtype=np.int16)
        sex_arr = np.empty(n_persons, dtype=np.int8)
        role_arr = np.empty(n_persons, dtype=np.int8)
        household_id_arr = np.empty(n_persons, dtype=np.int32)
        family_type_arr = np.empty(n_persons, dtype=np.int8)

        idx = 0
        for hh in households:
            ft_id = family_reg.id_of(hh.family_type)
            for person in hh.members:
                age_arr[idx] = person.age
                sex_arr[idx] = sex_reg.id_of(person.sex)
                role_arr[idx] = role_reg.id_of(person.role)
                household_id_arr[idx] = hh.household_id
                family_type_arr[idx] = ft_id
                idx += 1

        return cls(
            age=age_arr,
            sex=sex_arr,
            role=role_arr,
            household_id=household_id_arr,
            family_type=family_type_arr,
            _family_reg=family_reg,
            _role_reg=role_reg,
            _sex_reg=sex_reg,
        )

    def to_households(self) -> list[Household]:
        """並列配列から Pydantic の Household リストへ逆変換する.

        :class:`~synthpop_jp.domain.household.Household` のリストを返す。

        SA が完了した後、CSV 書き出しのために呼び出す。SA 内部では呼び出さない。

        Returns
        -------
        list[Household]
            household_id の出現順に並んだ世帯リスト。

        Notes
        -----
        同じ household_id を持つ person が連続していなくても正しく動作する。
        household_id の出現順序（最初に現れた順）で世帯を並べる。
        """
        from synthpop_jp.domain.household import Household
        from synthpop_jp.domain.person import Person

        if self.n_persons == 0:
            return []

        # household_id の出現順を保持しながら世帯ごとにグループ化
        # dict は Python 3.7+ で挿入順を保証する
        hh_members: dict[int, list[Person]] = {}
        hh_family_type: dict[int, str] = {}

        for i in range(self.n_persons):
            hid = int(self.household_id[i])
            if hid not in hh_members:
                hh_members[hid] = []
                hh_family_type[hid] = self._family_reg.name_of(int(self.family_type[i]))
            person = Person(
                household_id=hid,
                role=self._role_reg.name_of(int(self.role[i])),
                sex=self._sex_reg.name_of(int(self.sex[i])),  # type: ignore[arg-type]
                age=int(self.age[i]),
            )
            hh_members[hid].append(person)

        return [
            Household(
                household_id=hid,
                family_type=hh_family_type[hid],
                members=members,
            )
            for hid, members in hh_members.items()
        ]


@dataclass
class Proposal:
    """A proposed SA transition.

    Attributes
    ----------
    transition : str
        Name of the transition that produced this proposal.
    indices : np.ndarray
        Indices (into :class:`PopulationArrays`) affected by the proposal.
    before : np.ndarray
        Pre-change values (for reversal).
    after : np.ndarray
        Post-change values.
    """

    transition: str
    indices: np.ndarray[Any, Any]
    before: np.ndarray[Any, Any]
    after: np.ndarray[Any, Any]
