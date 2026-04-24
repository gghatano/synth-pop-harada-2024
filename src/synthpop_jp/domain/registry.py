"""文字列 ↔ 整数 ID の双方向マッピング（Registry）.

SA（シミュレーテッドアニーリング）の内部表現は NumPy 整数配列を使う（ADR-0001）。
このモジュールは family_type / role / sex といった文字列カテゴリを整数 ID に対応付け、
配列操作と pydantic ドメインモデルを橋渡しする。

基本的な使い方:

    >>> reg = StringRegistry()
    >>> mid = reg.register("single")
    >>> reg.id_of("single") == mid
    True
    >>> reg.name_of(mid) == "single"
    True
    >>> reg.id_of("unknown")  # KeyError
    Traceback (most recent call last):
        ...
    KeyError: 'unknown'

性・役割・家族類型には専用のサブクラスを使う:

    >>> sex_reg = SexRegistry()
    >>> sex_reg.id_of("M")
    0
    >>> sex_reg.id_of("F")
    1
"""

from __future__ import annotations

from typing import Final


class StringRegistry:
    """文字列 → 整数 ID の双方向マッピング.

    登録順に 0 から連番の ID を割り当てる。
    同じ名前を 2 回登録しても同じ ID が返る（idempotent）。

    Attributes
    ----------
    _name_to_id : dict[str, int]
        名前 → ID のマッピング。
    _id_to_name : dict[int, str]
        ID → 名前 のマッピング。
    """

    def __init__(self) -> None:
        self._name_to_id: dict[str, int] = {}
        self._id_to_name: dict[int, str] = {}

    def register(self, name: str) -> int:
        """名前を登録し、対応する整数 ID を返す.

        同じ名前を再登録しても同じ ID が返る（idempotent）。

        Parameters
        ----------
        name : str
            登録する名前（例: ``"single"``, ``"couple"``）。

        Returns
        -------
        int
            割り当てられた整数 ID（0 始まりの連番）。
        """
        if name in self._name_to_id:
            return self._name_to_id[name]
        new_id = len(self._name_to_id)
        self._name_to_id[name] = new_id
        self._id_to_name[new_id] = name
        return new_id

    def id_of(self, name: str) -> int:
        """登録済み名前から整数 ID を引く.

        Parameters
        ----------
        name : str
            登録済みの名前。

        Returns
        -------
        int
            対応する整数 ID。

        Raises
        ------
        KeyError
            名前が未登録の場合。
        """
        try:
            return self._name_to_id[name]
        except KeyError:
            raise KeyError(name) from None

    def name_of(self, id_: int) -> str:
        """整数 ID から名前を引く.

        Parameters
        ----------
        id_ : int
            登録済みの整数 ID。

        Returns
        -------
        str
            対応する名前。

        Raises
        ------
        KeyError
            ID が未登録の場合。
        """
        try:
            return self._id_to_name[id_]
        except KeyError:
            raise KeyError(id_) from None

    def all_names(self) -> set[str]:
        """登録済み名前の集合を返す.

        Returns
        -------
        set[str]
            登録済み名前の集合。
        """
        return set(self._name_to_id.keys())

    def __len__(self) -> int:
        """登録済み件数を返す."""
        return len(self._name_to_id)


class SexRegistry(StringRegistry):
    """性別 ↔ 整数 ID の Registry.

    ADR-0001 の sex 配列 dtype（int8）に合わせ、ID の割り当てを固定する:
    - ``"M"``（男性）→ 0
    - ``"F"``（女性）→ 1

    SA 内部では `arrays.sex[i] == 0` が男性、`== 1` が女性を意味する。
    """

    #: 男性の固定 ID
    M_ID: Final[int] = 0
    #: 女性の固定 ID
    F_ID: Final[int] = 1

    def __init__(self) -> None:
        super().__init__()
        self.register("M")  # → 0
        self.register("F")  # → 1


class RoleRegistry(StringRegistry):
    """役割 ↔ 整数 ID の Registry.

    役割の例: ``"husband"``, ``"wife"``, ``"child"``, ``"single"``。
    ID の割り当ては登録順（0 始まり）であり、固定しない。
    SA 実装者が必要な役割を事前に登録して使う。
    """


class FamilyTypeRegistry(StringRegistry):
    """家族類型 ↔ 整数 ID の Registry.

    家族類型の例: ``"single"``, ``"couple"``, ``"couple_and_children"``。
    ID の割り当ては登録順（0 始まり）であり、固定しない。
    SA 実装者が必要な家族類型を事前に登録して使う。
    """
