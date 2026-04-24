"""家族類型テンプレート定義.

9 種類の family_type それぞれに対して、世帯内の役割構成（roles）・
子どもを除いたコア人数（base_size）・子ども有無（has_children）を定義する。

``register_family_type(name, template)`` を使うと、新しい家族類型を追加できる。
SA の Phase 3 以降で独自の家族類型を試す際に利用する。

使い方::

    from synthpop_jp.domain.family_types import (
        FAMILY_TEMPLATES,
        FamilyTypeTemplate,
        register_family_type,
    )

    # 既存テンプレを参照する
    tmpl = FAMILY_TEMPLATES["couple"]
    print(tmpl.roles)  # ['husband', 'wife']

    # 独自テンプレを追加する
    custom = FamilyTypeTemplate(roles=["guardian", "child"], base_size=1, has_children=True)
    register_family_type("guardian_and_children", custom)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FamilyTypeTemplate:
    """1 つの家族類型のテンプレート.

    ``roles`` には「child を除いたコア役割」と「child 1 人分のプレースホルダ」を含む。
    実際の child 数は ``n_children`` で決まり、``expand_roles()`` が child を追加する。

    Attributes
    ----------
    roles : list[str]
        世帯員の役割リスト。「child」は 1 つだけ含め、追加の child は
        ``expand_roles()`` 内で n_children に応じて補完する。
    base_size : int
        子どもを除いたコア人数（例: couple_and_children なら 2）。
        ``base_size == len([r for r in roles if r != 'child'])`` が成立する。
    has_children : bool
        子ども人数を割り当てる対象かどうか。
        ``True`` のとき ``children_count_dist`` から子ども数をサンプリングする。
    """

    roles: list[str]
    base_size: int
    has_children: bool


#: 9 種類の family_type テンプレート辞書。
#: ``register_family_type()`` で追加できる。
FAMILY_TEMPLATES: dict[str, FamilyTypeTemplate] = {
    "single": FamilyTypeTemplate(
        roles=["single"],
        base_size=1,
        has_children=False,
    ),
    "couple": FamilyTypeTemplate(
        roles=["husband", "wife"],
        base_size=2,
        has_children=False,
    ),
    "couple_and_children": FamilyTypeTemplate(
        roles=["husband", "wife", "child"],
        base_size=2,
        has_children=True,
    ),
    "father_and_children": FamilyTypeTemplate(
        roles=["father", "child"],
        base_size=1,
        has_children=True,
    ),
    "mother_and_children": FamilyTypeTemplate(
        roles=["mother", "child"],
        base_size=1,
        has_children=True,
    ),
    "couple_and_parents": FamilyTypeTemplate(
        roles=["husband", "wife", "parent", "parent"],
        base_size=4,
        has_children=False,
    ),
    "couple_and_a_parent": FamilyTypeTemplate(
        roles=["husband", "wife", "parent"],
        base_size=3,
        has_children=False,
    ),
    "couple_children_and_parents": FamilyTypeTemplate(
        roles=["husband", "wife", "child", "parent", "parent"],
        base_size=4,
        has_children=True,
    ),
    "couple_children_and_a_parent": FamilyTypeTemplate(
        roles=["husband", "wife", "child", "parent"],
        base_size=3,
        has_children=True,
    ),
}


def register_family_type(name: str, template: FamilyTypeTemplate) -> None:
    """新しい家族類型テンプレートをグローバル辞書に登録する.

    同じ名前を再登録するとテンプレートが上書きされる。

    Parameters
    ----------
    name : str
        登録する家族類型名（例: ``"guardian_and_children"``）。
    template : FamilyTypeTemplate
        登録するテンプレート。
    """
    FAMILY_TEMPLATES[name] = template
