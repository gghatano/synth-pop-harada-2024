"""pydantic v2 モデル — 入力 CSV の行スキーマ定義.

各モデルは ``data_contract.md`` で定義された列・型・値域に対応する。
ローダ（``loaders.py``）が ``TypeAdapter`` / ``model_validate`` でこれらを使う。

couple_diff の符号規則
    ``couple_diff = husband_age - wife_age``（夫の年齢 − 妻の年齢）。
    夫が年上なら正、妻が年上なら負。``data_contract.md`` §4 で確定済み。
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# 必須 CSV 5 種
# ---------------------------------------------------------------------------


class FamilyTypeCountRow(BaseModel):
    """family_type_counts.csv の 1 行.

    Attributes
    ----------
    family_type : str
        家族類型名（例: ``"single"``, ``"couple_and_children"``）。
    count : int
        世帯数。0 以上の整数。
    """

    family_type: str
    count: Annotated[int, Field(ge=0)]


class ChildrenCountDistRow(BaseModel):
    """children_count_dist.csv の 1 行.

    子ども人数分布を family_type_group 別に表す。

    Attributes
    ----------
    family_type_group : str
        家族類型グループ（``configs/family_type_mapping.yaml`` で定義）。
    n_children : int
        子どもの人数。0 以上の整数。
    rate : float
        その人数の割合。0.0 以上 1.0 以下。
    """

    family_type_group: str
    n_children: Annotated[int, Field(ge=0)]
    rate: Annotated[float, Field(ge=0.0, le=1.0)]


class DemographicByAgeSexRow(BaseModel):
    """demographic_by_age_sex.csv の 1 行.

    年齢・性別別の人口を表す。

    Attributes
    ----------
    age : int
        年齢（歳）。0 以上 120 以下。
    sex : Literal["M", "F"]
        性別。``"M"`` = 男性、``"F"`` = 女性。
    count : int
        人口。0 以上の整数。
    """

    age: Annotated[int, Field(ge=0, le=120)]
    sex: Literal["M", "F"]
    count: Annotated[int, Field(ge=0)]


class AgeDiffParentChildRow(BaseModel):
    """age_diff_parent_child.csv の 1 行.

    親子年齢差の分布を role 別に表す。

    diff は ``parent_age - child_age``（親の年齢 − 子の年齢）。
    半開区間 ``[diff_min, diff_max)`` で表現する。

    Attributes
    ----------
    role : Literal["father", "mother"]
        親の役割。
    diff_min : int
        年齢差の下限（含む）。
    diff_max : int
        年齢差の上限（含まない）。diff_min より大きい必要がある。
    count : int
        観測数。0 以上の整数。
    """

    role: Literal["father", "mother"]
    diff_min: int
    diff_max: int
    count: Annotated[int, Field(ge=0)]

    def model_post_init(self, __context: object) -> None:
        """diff_min < diff_max を検証する."""
        if self.diff_min >= self.diff_max:
            msg = (
                f"diff_min ({self.diff_min}) は"
                f" diff_max ({self.diff_max}) より小さくなければなりません"
            )
            raise ValueError(msg)


class AgeDiffCoupleRow(BaseModel):
    """age_diff_couple.csv の 1 行.

    夫婦年齢差の分布を表す。

    符号規則: ``couple_diff = husband_age - wife_age``。
    夫が年上なら正、妻が年上なら負（``data_contract.md`` §4 参照）。
    半開区間 ``[diff_min, diff_max)`` で表現する。

    Attributes
    ----------
    diff_min : int
        年齢差の下限（含む）。husband_age - wife_age の最小値。
    diff_max : int
        年齢差の上限（含まない）。diff_min より大きい必要がある。
    count : int
        観測数。0 以上の整数。
    """

    diff_min: int
    diff_max: int
    count: Annotated[int, Field(ge=0)]

    def model_post_init(self, __context: object) -> None:
        """diff_min < diff_max を検証する."""
        if self.diff_min >= self.diff_max:
            msg = (
                f"diff_min ({self.diff_min}) は"
                f" diff_max ({self.diff_max}) より小さくなければなりません"
            )
            raise ValueError(msg)


# ---------------------------------------------------------------------------
# 任意 CSV 2 種
# ---------------------------------------------------------------------------


class DemographicByFamilyTypeRoleRow(BaseModel):
    """demographic_by_family_type_role.csv の 1 行（任意入力）.

    家族類型 × 役割 × 性別 × 年齢 別の人口分布。

    Attributes
    ----------
    family_type : str
        家族類型名。
    role : str
        役割（例: ``"husband"``, ``"child"``）。
    sex : Literal["M", "F"]
        性別。
    age : int
        年齢（歳）。0 以上 120 以下。
    count : int
        人口。0 以上の整数。
    """

    family_type: str
    role: str
    sex: Literal["M", "F"]
    age: Annotated[int, Field(ge=0, le=120)]
    count: Annotated[int, Field(ge=0)]


class HouseholdSizeByFamilyTypeRow(BaseModel):
    """household_size_by_family_type.csv の 1 行（任意入力）.

    家族類型別の世帯人数分布。

    Attributes
    ----------
    family_type : str
        家族類型名。
    household_size : int
        世帯人数。1 以上の整数。
    count : int
        世帯数。0 以上の整数。
    """

    family_type: str
    household_size: Annotated[int, Field(ge=1)]
    count: Annotated[int, Field(ge=0)]
