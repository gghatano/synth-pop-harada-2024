"""世帯サンプラ — §10.1 Step 1〜4 の pure 関数群.

6 ステップ中の前半 4 ステップを実装する。
全関数は pure（副作用なし）であり、乱数を使わない。

Step 1: ``assign_household_counts()`` — family_type 別世帯数の確定
Step 2: ``assign_household_sizes()`` — 世帯サイズの割当（Largest Remainder 法）
Step 3: ``assign_children_counts()`` — children 数の割付（Largest Remainder 法）
Step 4: ``expand_roles()`` — family_type テンプレから role 列を決定論的に展開

Largest Remainder 法について:
    分数配分（例: 30 世帯の 33.3% = 10.0 世帯）を整数に丸めるとき、
    単純な floor 丸めでは合計が足りなくなる。Largest Remainder 法は
    「小数部が大きい順に 1 ずつ追加」することで合計を保証する。
    これにより「入力統計との完全一致」が成立する。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from synthpop_jp.domain.family_types import FAMILY_TEMPLATES
from synthpop_jp.io.schemas import (
    ChildrenCountDistRow,
    FamilyTypeCountRow,
    HouseholdSizeByFamilyTypeRow,
)

# ---------------------------------------------------------------------------
# 中間データ構造
# ---------------------------------------------------------------------------


@dataclass
class HouseholdPlan:
    """1 世帯の計画（Step 1〜3 の出力）.

    Attributes
    ----------
    family_type : str
        家族類型名。
    household_size : int
        世帯人数（children を含む）。
    n_children : int
        割り当てられた子ども数。0 の場合は子なし。
    """

    family_type: str
    household_size: int
    n_children: int = 0


@dataclass
class HouseholdRoleEntry:
    """1 世帯の計画 + 展開済み roles（Step 4 の出力）.

    Attributes
    ----------
    plan : HouseholdPlan
        元の世帯計画。
    roles : list[str]
        世帯員の役割リスト（順序は template 通り）。
    """

    plan: HouseholdPlan
    roles: list[str] = field(default_factory=lambda: [])


@dataclass
class HouseholdSexEntry:
    """1 世帯の計画 + roles + sex（Step 5 の出力）.

    Attributes
    ----------
    plan : HouseholdPlan
        元の世帯計画。
    roles : list[str]
        世帯員の役割リスト。
    sexes : list[str]
        世帯員の性別リスト（'M' または 'F'）。
    """

    plan: HouseholdPlan
    roles: list[str]
    sexes: list[str] = field(default_factory=lambda: [])


@dataclass
class HouseholdAgeEntry:
    """1 世帯の計画 + roles + sex + age（Step 6 の出力）.

    Attributes
    ----------
    plan : HouseholdPlan
        元の世帯計画。
    roles : list[str]
        世帯員の役割リスト。
    sexes : list[str]
        世帯員の性別リスト。
    ages : list[int]
        世帯員の年齢リスト。
    """

    plan: HouseholdPlan
    roles: list[str]
    sexes: list[str]
    ages: list[int] = field(default_factory=lambda: [])


# ---------------------------------------------------------------------------
# ユーティリティ
# ---------------------------------------------------------------------------


def largest_remainder(rates: np.ndarray, total: int) -> np.ndarray:
    """比率配列を Largest Remainder 法で整数割付する.

    ``rates`` の各要素を ``total`` に比例配分し、合計が ``total`` になるよう
    整数で割り付ける。単純な floor 丸めでは合計が不足する場合、小数部が
    大きい順に 1 を加算して合計を補正する。

    Parameters
    ----------
    rates : np.ndarray
        比率の配列。各要素は 0 以上で、合計が 1 に近い値を期待する。
    total : int
        割り付ける総数。0 以上の整数。

    Returns
    -------
    np.ndarray
        ``int`` 型の割付結果。shape は ``rates`` と同じ。合計は ``total`` に等しい。

    Examples
    --------
    >>> import numpy as np
    >>> rates = np.array([0.5, 0.3, 0.2])
    >>> largest_remainder(rates, 10)
    array([5, 3, 2])

    >>> rates = np.array([1 / 3, 1 / 3, 1 / 3])
    >>> largest_remainder(rates, 3)
    array([1, 1, 1])
    """
    if total == 0:
        return np.zeros(len(rates), dtype=int)

    quotients = rates * total
    floors = np.floor(quotients).astype(int)
    remainders = quotients - floors
    deficit = int(total - floors.sum())

    if deficit > 0:
        top_indices = np.argsort(-remainders)[:deficit]
        floors[top_indices] += 1

    return floors


# ---------------------------------------------------------------------------
# Step 1: family_type 別世帯数の確定
# ---------------------------------------------------------------------------


def assign_household_counts(
    family_type_counts: list[FamilyTypeCountRow],
) -> dict[str, int]:
    """CSV の family_type 別世帯数をそのまま辞書として返す（Step 1）.

    入力統計を変更せず、辞書に変換するだけ。これにより family_type 別世帯数は
    常に入力と完全一致する。

    Parameters
    ----------
    family_type_counts : list[FamilyTypeCountRow]
        ``family_type_counts.csv`` から読み込んだ行モデルのリスト。

    Returns
    -------
    dict[str, int]
        ``{family_type: 世帯数}`` の辞書。
    """
    return {row.family_type: row.count for row in family_type_counts}


# ---------------------------------------------------------------------------
# Step 2: household size の割当
# ---------------------------------------------------------------------------


def assign_household_sizes(
    hh_counts: dict[str, int],
    hh_size_rows: list[HouseholdSizeByFamilyTypeRow] | None,
) -> list[HouseholdPlan]:
    """各世帯に household_size を割り当てる（Step 2）.

    ``hh_size_rows`` が与えられた場合は Largest Remainder 法で分布通りに割付。
    ``None`` の場合は ``FAMILY_TEMPLATES`` の ``base_size`` を使用する。

    Parameters
    ----------
    hh_counts : dict[str, int]
        Step 1 で確定した family_type 別世帯数。
    hh_size_rows : list[HouseholdSizeByFamilyTypeRow] | None
        ``household_size_by_family_type.csv`` から読み込んだ行モデル。
        ``None`` の場合はデフォルトサイズを使用する。

    Returns
    -------
    list[HouseholdPlan]
        各世帯の計画リスト。合計長は ``sum(hh_counts.values())`` に等しい。
    """
    plans: list[HouseholdPlan] = []

    if hh_size_rows is not None:
        # family_type ごとに size 分布を辞書化する
        size_dist: dict[str, dict[int, int]] = {}
        for row in hh_size_rows:
            if row.family_type not in size_dist:
                size_dist[row.family_type] = {}
            size_dist[row.family_type][row.household_size] = row.count

        for ft, count in hh_counts.items():
            if count == 0:
                continue
            if size_dist.get(ft):
                # Largest Remainder で count 世帯を size 別に配分
                sizes = sorted(size_dist[ft].keys())
                raw_counts = np.array([size_dist[ft][s] for s in sizes], dtype=float)
                total_raw = raw_counts.sum()
                if total_raw > 0:
                    rates = raw_counts / total_raw
                else:
                    # 全て 0 の場合はテンプレのデフォルトを使う
                    tmpl = FAMILY_TEMPLATES.get(ft)
                    base = tmpl.base_size if tmpl else 1
                    plans.extend(
                        HouseholdPlan(family_type=ft, household_size=base) for _ in range(count)
                    )
                    continue
                allocated = largest_remainder(rates, count)
                for sz, n in zip(sizes, allocated, strict=True):
                    plans.extend(HouseholdPlan(family_type=ft, household_size=sz) for _ in range(n))
            else:
                # size 分布がない場合はテンプレのデフォルトを使う
                tmpl = FAMILY_TEMPLATES.get(ft)
                base = tmpl.base_size if tmpl else 1
                plans.extend(
                    HouseholdPlan(family_type=ft, household_size=base) for _ in range(count)
                )
    else:
        # CSV なし: テンプレのデフォルト base_size を使う
        for ft, count in hh_counts.items():
            if count == 0:
                continue
            tmpl = FAMILY_TEMPLATES.get(ft)
            base = tmpl.base_size if tmpl else 1
            plans.extend(HouseholdPlan(family_type=ft, household_size=base) for _ in range(count))

    return plans


# ---------------------------------------------------------------------------
# Step 3: children 数の割付
# ---------------------------------------------------------------------------


def assign_children_counts(
    plans: list[HouseholdPlan],
    children_count_dist: list[ChildrenCountDistRow],
    family_type_mapping: dict[str, str],
) -> list[HouseholdPlan]:
    """with_children の世帯に children 数を割り付ける（Step 3）.

    割付モードは以下の 2 通りある:

    **モード A（household_size が base_size より大きい場合）**:
        Step 2 で household_size が CSV から確定済みのため、
        ``n_children = household_size - base_size`` を計算する（決定論的）。
        ``children_count_dist`` は参照しない。

    **モード B（household_size == base_size の場合）**:
        Step 2 で CSV なしのフォールバック（全世帯が base_size）のため、
        ``children_count_dist`` の分布を Largest Remainder 法で割り付け、
        ``household_size = base_size + n_children`` に更新する。

    ``without_children`` / ``single`` グループの世帯は n_children=0 のまま。

    Parameters
    ----------
    plans : list[HouseholdPlan]
        Step 2 の出力。household_size 割付済みの世帯計画リスト。
    children_count_dist : list[ChildrenCountDistRow]
        ``children_count_dist.csv`` から読み込んだ行モデル。
        モード A では参照しない（household_size から導出するため）。
    family_type_mapping : dict[str, str]
        ``{family_type: family_type_group}`` のマッピング辞書。

    Returns
    -------
    list[HouseholdPlan]
        ``n_children`` が設定された世帯計画リスト。
    """
    result: list[HouseholdPlan] = []

    # with_children グループの children 数分布を取得（モード B 用）
    children_dist_map: dict[str, dict[int, float]] = {}
    for row in children_count_dist:
        if row.family_type_group not in children_dist_map:
            children_dist_map[row.family_type_group] = {}
        children_dist_map[row.family_type_group][row.n_children] = row.rate

    # with_children の世帯インデックスを収集（モード A / B 判定のため）
    with_children_indices_mode_b: list[int] = []

    for _i, p in enumerate(plans):
        group = family_type_mapping.get(p.family_type, "")
        tmpl = FAMILY_TEMPLATES.get(p.family_type)
        base_size = tmpl.base_size if tmpl else 1

        if group == "with_children":
            if p.household_size > base_size:
                # モード A: household_size から n_children を導出
                n_child = p.household_size - base_size
                result.append(
                    HouseholdPlan(
                        family_type=p.family_type,
                        household_size=p.household_size,
                        n_children=n_child,
                    )
                )
            else:
                # モード B: children_count_dist で後から割付
                with_children_indices_mode_b.append(len(result))
                result.append(
                    HouseholdPlan(
                        family_type=p.family_type,
                        household_size=p.household_size,
                        n_children=0,
                    )
                )
        else:
            # without_children / single: n_children=0 のまま
            result.append(
                HouseholdPlan(
                    family_type=p.family_type,
                    household_size=p.household_size,
                    n_children=0,
                )
            )

    # モード B の世帯に Largest Remainder で children 数を割付
    if with_children_indices_mode_b:
        total = len(with_children_indices_mode_b)
        group = "with_children"
        dist = children_dist_map.get(group, {})

        if dist:
            n_children_values = sorted(k for k in dist if k > 0 or len(dist) == 1)
            rates = np.array([dist[n] for n in n_children_values], dtype=float)
            if rates.sum() > 0:
                rates = rates / rates.sum()
            allocated = largest_remainder(rates, total)

            idx_iter = iter(with_children_indices_mode_b)
            for n_child, count in zip(n_children_values, allocated, strict=True):
                for _ in range(int(count)):
                    plan_idx = next(idx_iter)
                    p = result[plan_idx]
                    tmpl = FAMILY_TEMPLATES.get(p.family_type)
                    base_size = tmpl.base_size if tmpl else 1
                    result[plan_idx] = HouseholdPlan(
                        family_type=p.family_type,
                        household_size=base_size + n_child,
                        n_children=n_child,
                    )

    return result


# ---------------------------------------------------------------------------
# Step 4: role 展開
# ---------------------------------------------------------------------------


def expand_roles(plans: list[HouseholdPlan]) -> list[HouseholdRoleEntry]:
    """family_type テンプレから各世帯の roles を決定論的に展開する（Step 4）.

    ``FAMILY_TEMPLATES`` の ``roles`` を基に、``n_children`` 分の ``'child'`` を
    追加して各世帯員の役割リストを生成する。

    ``household_size`` に対して roles の長さが合わない場合は、
    ``household_size`` になるよう最後の役割を繰り返す（フォールバック）。

    Parameters
    ----------
    plans : list[HouseholdPlan]
        Step 3 の出力。n_children 割付済みの世帯計画リスト。

    Returns
    -------
    list[HouseholdRoleEntry]
        各世帯の役割展開結果。
    """
    entries: list[HouseholdRoleEntry] = []

    for plan in plans:
        tmpl = FAMILY_TEMPLATES.get(plan.family_type)
        if tmpl is None:
            # 未知の family_type: 全員 "unknown"
            roles = ["unknown"] * plan.household_size
            entries.append(HouseholdRoleEntry(plan=plan, roles=roles))
            continue

        if tmpl.has_children:
            # child を除いたコア roles を作成
            core_roles = [r for r in tmpl.roles if r != "child"]
            # n_children 分の child を追加
            n_child = max(plan.n_children, 1)  # 最低 1 人の child
            roles = core_roles + ["child"] * n_child
        else:
            roles = list(tmpl.roles)

        # household_size に合わせて調整
        if len(roles) < plan.household_size:
            # 不足分は最後の role を繰り返す
            last_role = roles[-1] if roles else "unknown"
            roles += [last_role] * (plan.household_size - len(roles))
        elif len(roles) > plan.household_size:
            # 超過分は切り捨て
            roles = roles[: plan.household_size]

        # household_size 一致保証: n_children を roles の child 数に合わせる
        n_child_actual = roles.count("child")
        if n_child_actual != plan.n_children:
            plan = HouseholdPlan(
                family_type=plan.family_type,
                household_size=plan.household_size,
                n_children=n_child_actual,
            )

        entries.append(HouseholdRoleEntry(plan=plan, roles=roles))

    return entries
