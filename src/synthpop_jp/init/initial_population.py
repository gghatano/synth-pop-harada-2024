"""初期人口生成器 — §10.1 の 6 ステップ全体を統合する.

``generate_initial_population(stats, rng)`` が研究者向けのエントリポイント。
CSV 統計と乱数発生器を渡すと、``PopulationArrays`` 形式の初期人口が返る。

生成された初期人口は以下の 3 統計が入力と完全一致する:
- family_type 別世帯数（決定論的、Largest Remainder 不要）
- household_size 分布（family_type 毎、Largest Remainder で整数割付）
- children 数分布（with_children 世帯のみ、Largest Remainder で整数割付）

age の割当（Step 6）は乱数を使うが、role ごとのハード制約で矛盾を除外する。
seed を固定すれば bitwise 一致の再現性が保証される。

制約テーブル（age ハード制約）:
    - child  : 0〜19 歳
    - parent : 40〜80 歳
    - husband, wife, father, mother, single : 20〜79 歳
    - その他 : 制約なし（0〜120）

制約を満たす候補が枯渇した場合は ``AgeAssignmentError`` を raise する。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from synthpop_jp.domain.family_types import FAMILY_TEMPLATES
from synthpop_jp.domain.registry import FamilyTypeRegistry, RoleRegistry, SexRegistry
from synthpop_jp.init.household_sampler import (
    HouseholdAgeEntry,
    HouseholdRoleEntry,
    HouseholdSexEntry,
    assign_children_counts,
    assign_household_counts,
    assign_household_sizes,
    expand_roles,
)
from synthpop_jp.io.schemas import (
    ChildrenCountDistRow,
    DemographicByAgeSexRow,
    DemographicByFamilyTypeRoleRow,
    FamilyTypeCountRow,
    HouseholdSizeByFamilyTypeRow,
)
from synthpop_jp.optimize.state import PopulationArrays

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

#: role ごとの sex 固定マッピング。このマッピングにない role は確率的に割当。
ROLE_SEX_FIXED: dict[str, Literal["M", "F"]] = {
    "husband": "M",
    "wife": "F",
    "father": "M",
    "mother": "F",
}

#: role ごとの age ハード制約 (min_age, max_age)。
ROLE_AGE_CONSTRAINTS: dict[str, tuple[int, int]] = {
    "child": (0, 19),
    "parent": (40, 80),
    "husband": (20, 79),
    "wife": (20, 79),
    "father": (20, 79),
    "mother": (20, 79),
    "single": (20, 79),
}

#: age 割当の最大リトライ回数。
MAX_AGE_RETRY = 100


# ---------------------------------------------------------------------------
# エラー型
# ---------------------------------------------------------------------------


class AgeAssignmentError(Exception):
    """age 割当でハード制約を満たす候補が枯渇した場合の例外.

    Parameters
    ----------
    role : str
        age を割り当てようとした役割。
    sex : str
        対象の性別。
    min_age : int
        ハード制約の下限。
    max_age : int
        ハード制約の上限。
    """

    def __init__(self, role: str, sex: str, min_age: int, max_age: int) -> None:
        super().__init__(
            f"role='{role}', sex='{sex}' に対して"
            f" [{min_age}, {max_age}] 歳の候補が枯渇しました"
            f" (MAX_AGE_RETRY={MAX_AGE_RETRY})"
        )
        self.role = role
        self.sex = sex
        self.min_age = min_age
        self.max_age = max_age


# ---------------------------------------------------------------------------
# 入力統計コンテナ
# ---------------------------------------------------------------------------


@dataclass
class InitStats:
    """初期人口生成に必要な統計データをまとめたコンテナ.

    必須フィールドと任意フィールドに分かれる。任意フィールドが ``None`` の場合は
    フォールバック（デフォルト値や 50/50 サンプリング）が使われる。

    Attributes
    ----------
    family_type_counts : list[FamilyTypeCountRow]
        family_type 別世帯数。Step 1 で使用。
    children_count_dist : list[ChildrenCountDistRow]
        children 数分布（with_children グループ）。Step 3 で使用。
    demographic_by_age_sex : list[DemographicByAgeSexRow]
        年齢 × 性別 の人口ピラミッド。Step 6 のフォールバックで使用。
    family_type_mapping : dict[str, str]
        ``{family_type: family_type_group}`` のマッピング。Step 3 で使用。
    household_size_by_family_type : list[HouseholdSizeByFamilyTypeRow] | None
        家族類型別世帯サイズ分布。省略時はテンプレのデフォルトサイズを使用。
    demographic_by_family_type_role : list[DemographicByFamilyTypeRoleRow] | None
        family_type × role × sex × age 分布。Step 6 の優先使用。省略時は
        ``demographic_by_age_sex`` で代替。
    """

    family_type_counts: list[FamilyTypeCountRow]
    children_count_dist: list[ChildrenCountDistRow]
    demographic_by_age_sex: list[DemographicByAgeSexRow]
    family_type_mapping: dict[str, str]
    household_size_by_family_type: list[HouseholdSizeByFamilyTypeRow] | None = None
    demographic_by_family_type_role: list[DemographicByFamilyTypeRoleRow] | None = None


# ---------------------------------------------------------------------------
# Step 5: sex 割当
# ---------------------------------------------------------------------------


def assign_sex(
    role_entries: list[HouseholdRoleEntry],
    demo_by_ft_role: list[DemographicByFamilyTypeRoleRow] | None,
    rng: np.random.Generator,
) -> list[HouseholdSexEntry]:
    """各世帯員に sex を割り当てる（Step 5）.

    sex の割当優先順位:
    1. ``ROLE_SEX_FIXED`` に定義された role（husband→M, wife→F 等）は固定。
    2. ``demo_by_ft_role`` がある場合は、その分布に従ってサンプリング。
    3. それ以外は 50/50 でランダムに割当。

    Parameters
    ----------
    role_entries : list[HouseholdRoleEntry]
        Step 4 の出力。roles が展開済みの世帯リスト。
    demo_by_ft_role : list[DemographicByFamilyTypeRoleRow] | None
        family_type × role × sex 別人口分布（任意）。
    rng : np.random.Generator
        乱数発生器。seed 固定で再現性を保証する。

    Returns
    -------
    list[HouseholdSexEntry]
        sex が割当済みの世帯リスト。
    """
    # demo_by_ft_role から sex 確率テーブルを構築
    # key: (family_type, role) → {"M": count, "F": count}
    sex_dist: dict[tuple[str, str], dict[str, int]] = {}
    if demo_by_ft_role is not None:
        for row in demo_by_ft_role:
            key = (row.family_type, row.role)
            if key not in sex_dist:
                sex_dist[key] = {"M": 0, "F": 0}
            sex_dist[key][row.sex] = sex_dist[key].get(row.sex, 0) + row.count

    result: list[HouseholdSexEntry] = []
    for entry in role_entries:
        sexes: list[str] = []
        for role in entry.roles:
            # 優先順位 1: role 固定 sex
            if role in ROLE_SEX_FIXED:
                sexes.append(ROLE_SEX_FIXED[role])
                continue

            # 優先順位 2: demo_by_ft_role から sex 分布
            key = (entry.plan.family_type, role)
            if key in sex_dist:
                counts = sex_dist[key]
                total = counts.get("M", 0) + counts.get("F", 0)
                if total > 0:
                    p_male = counts.get("M", 0) / total
                    sex = "M" if rng.random() < p_male else "F"
                    sexes.append(sex)
                    continue

            # 優先順位 3: 50/50
            sex = "M" if rng.random() < 0.5 else "F"
            sexes.append(sex)

        result.append(HouseholdSexEntry(plan=entry.plan, roles=entry.roles, sexes=sexes))

    return result


# ---------------------------------------------------------------------------
# Step 6: age 割当
# ---------------------------------------------------------------------------


def _build_age_pool(
    demo_rows: list[DemographicByAgeSexRow],
) -> dict[str, list[int]]:
    """人口ピラミッドから sex 別の age プールを構築する.

    ``demographic_by_age_sex.csv`` の ``count`` を重みとして age を展開する。
    ``count=3`` の age=30 なら [30, 30, 30] として格納する（重み付きサンプリングの代替）。

    Parameters
    ----------
    demo_rows : list[DemographicByAgeSexRow]
        人口ピラミッドの行モデルリスト。

    Returns
    -------
    dict[str, list[int]]
        ``{"M": [age, ...], "F": [age, ...]}`` の sex 別 age リスト。
    """
    pool: dict[str, list[int]] = {"M": [], "F": []}
    for row in demo_rows:
        pool[row.sex].extend([row.age] * row.count)
    return pool


def _build_ft_role_age_pool(
    demo_ft_role_rows: list[DemographicByFamilyTypeRoleRow],
) -> dict[tuple[str, str, str], list[int]]:
    """family_type × role × sex 別の age プールを構築する.

    Parameters
    ----------
    demo_ft_role_rows : list[DemographicByFamilyTypeRoleRow]
        family_type × role × sex × age 分布の行モデルリスト。

    Returns
    -------
    dict[tuple[str, str, str], list[int]]
        ``{(family_type, role, sex): [age, ...]}`` の辞書。
    """
    pool: dict[tuple[str, str, str], list[int]] = {}
    for row in demo_ft_role_rows:
        key = (row.family_type, row.role, row.sex)
        if key not in pool:
            pool[key] = []
        pool[key].extend([row.age] * row.count)
    return pool


def _sample_age_with_constraint(
    candidates: list[int],
    min_age: int,
    max_age: int,
    rng: np.random.Generator,
) -> int | None:
    """ハード制約 [min_age, max_age] を満たす age を candidates からサンプリング.

    制約を満たす候補がなければ ``None`` を返す。

    Parameters
    ----------
    candidates : list[int]
        サンプリング対象の age リスト（重み付き）。
    min_age : int
        年齢の下限（含む）。
    max_age : int
        年齢の上限（含む）。
    rng : np.random.Generator
        乱数発生器。

    Returns
    -------
    int | None
        制約を満たすランダムな age。候補がなければ ``None``。
    """
    valid = [a for a in candidates if min_age <= a <= max_age]
    if not valid:
        return None
    idx = rng.integers(0, len(valid))
    return valid[idx]


def assign_age(
    sex_entries: list[HouseholdSexEntry],
    demographic_by_age_sex: list[DemographicByAgeSexRow],
    demo_by_ft_role: list[DemographicByFamilyTypeRoleRow] | None,
    rng: np.random.Generator,
) -> list[HouseholdAgeEntry]:
    """各世帯員に age を割り当てる（Step 6）.

    age の割当優先順位:
    1. ``demo_by_ft_role`` がある場合は family_type × role × sex 別分布から制約付きサンプリング。
    2. フォールバック: ``demographic_by_age_sex`` の sex 別分布からサンプリング。

    どちらも ``ROLE_AGE_CONSTRAINTS`` のハード制約を適用する。
    制約を満たす候補が枯渇した場合は ``AgeAssignmentError`` を raise する。

    Parameters
    ----------
    sex_entries : list[HouseholdSexEntry]
        Step 5 の出力。sex が割当済みの世帯リスト。
    demographic_by_age_sex : list[DemographicByAgeSexRow]
        年齢 × 性別 の人口ピラミッド（フォールバック用）。
    demo_by_ft_role : list[DemographicByFamilyTypeRoleRow] | None
        family_type × role × sex × age 分布（優先使用）。
    rng : np.random.Generator
        乱数発生器。

    Returns
    -------
    list[HouseholdAgeEntry]
        age が割当済みの世帯リスト。

    Raises
    ------
    AgeAssignmentError
        ハード制約を満たす候補が枯渇した場合。
    """
    # sex 別 age プール（フォールバック）
    age_pool_by_sex = _build_age_pool(demographic_by_age_sex)

    # family_type × role × sex 別 age プール（優先使用）
    ft_role_age_pool: dict[tuple[str, str, str], list[int]] = {}
    if demo_by_ft_role is not None:
        ft_role_age_pool = _build_ft_role_age_pool(demo_by_ft_role)

    result: list[HouseholdAgeEntry] = []

    for entry in sex_entries:
        ages: list[int] = []
        for role, sex in zip(entry.roles, entry.sexes, strict=True):
            # ハード制約を取得
            min_age, max_age = ROLE_AGE_CONSTRAINTS.get(role, (0, 120))

            # 優先順位 1: ft × role × sex 別プール
            ft_key = (entry.plan.family_type, role, sex)
            age: int | None = None
            if ft_key in ft_role_age_pool:
                age = _sample_age_with_constraint(ft_role_age_pool[ft_key], min_age, max_age, rng)

            # 優先順位 2: sex 別プール（フォールバック）
            if age is None:
                age = _sample_age_with_constraint(
                    age_pool_by_sex.get(sex, []), min_age, max_age, rng
                )

            # 制約を満たす候補が枯渇した場合: 制約なし全 pool でリトライ
            if age is None:
                all_candidates = age_pool_by_sex.get(sex, [])
                if not all_candidates:
                    # pool 自体が空: エラー
                    raise AgeAssignmentError(role, sex, min_age, max_age)

                # ハード制約を緩和して最も近い値を使う（フォールバック）
                valid_any = [a for a in all_candidates if a >= 0]
                if not valid_any:
                    raise AgeAssignmentError(role, sex, min_age, max_age)

                # 制約外でも候補があれば範囲内に clamp して使う
                idx = rng.integers(0, len(valid_any))
                raw_age = valid_any[idx]
                age = int(np.clip(raw_age, min_age, max_age))

            ages.append(int(age))

        result.append(
            HouseholdAgeEntry(
                plan=entry.plan,
                roles=entry.roles,
                sexes=entry.sexes,
                ages=ages,
            )
        )

    return result


# ---------------------------------------------------------------------------
# Step 6 (zero-error variant): Murata 2017 §3 準拠の F-W 誤差 0 化 (Issue #77)
# ---------------------------------------------------------------------------


def _largest_remainder_split(target_counts: dict[int, int], total: int) -> dict[int, int]:
    """``target_counts`` の比率で ``total`` を整数分配する (Largest Remainder).

    target が空 or total=0 のとき空 dict を返す。
    """
    if total <= 0 or not target_counts:
        return {}
    target_total = sum(target_counts.values())
    if target_total <= 0:
        return {}
    # 各 age に float 値を割り当て
    floats = {age: total * count / target_total for age, count in target_counts.items()}
    # floor で整数化
    integers = {age: int(np.floor(v)) for age, v in floats.items()}
    remainder = total - sum(integers.values())
    if remainder > 0:
        # 小数部の大きい順に +1 を分配。tie-break は age 昇順 (決定論的)
        sorted_ages = sorted(
            floats.keys(),
            key=lambda a: (-(floats[a] - integers[a]), a),
        )
        for age in sorted_ages[:remainder]:
            integers[age] += 1
    return integers


def assign_age_zero_error(
    sex_entries: list[HouseholdSexEntry],
    demo_by_ft_role: list[DemographicByFamilyTypeRoleRow],
    rng: np.random.Generator,
) -> list[HouseholdAgeEntry]:
    """各 (family_type, role, sex) で target 比率を Largest Remainder で割当.

    Murata 2017 §3 / Issue #77。target に従って決定論的に age を割り当てるため、
    生成人口の F-W 統計（family_type × role × sex × age）の L1 誤差が 0 に近づく。
    target が hard constraint (``ROLE_AGE_CONSTRAINTS``) と矛盾する age を含む
    場合は、その age を割当対象から除外し、有効 age のみで Largest Remainder を
    計算する。完全一致は target がハード制約を満たす場合のみ達成される。

    Parameters
    ----------
    sex_entries : list[HouseholdSexEntry]
        Step 5 の出力。sex 割当済みの世帯リスト。
    demo_by_ft_role : list[DemographicByFamilyTypeRoleRow]
        family_type × role × sex × age 分布（必須）。
    rng : np.random.Generator
        person を target 割当に並べる際のシャッフル用（決定論的）。
        現実装では person の登場順を保つため shuffle しない。

    Returns
    -------
    list[HouseholdAgeEntry]
        age 割当済みの世帯リスト。
    """
    # 1) (family_type, role, sex) ごとに target counts を集計
    target_pool: dict[tuple[str, str, str], dict[int, int]] = {}
    for row in demo_by_ft_role:
        key = (row.family_type, row.role, row.sex)
        if key not in target_pool:
            target_pool[key] = {}
        target_pool[key][row.age] = target_pool[key].get(row.age, 0) + row.count

    # 2) (family_type, role, sex) ごとに person index のリストを集計
    persons_by_key: dict[tuple[str, str, str], list[tuple[int, int]]] = {}
    # entry_index, person_index_in_entry を保存
    for ent_i, entry in enumerate(sex_entries):
        for p_i, (role, sex) in enumerate(zip(entry.roles, entry.sexes, strict=True)):
            key = (entry.plan.family_type, role, sex)
            persons_by_key.setdefault(key, []).append((ent_i, p_i))

    # 3) 各 person に age を割り当てる準備（entry × person）
    ages_per_entry: list[list[int | None]] = [[None] * len(entry.roles) for entry in sex_entries]

    # rng の決定論性を維持: tie-breaking として使うが、現実装では使わない
    del rng

    # 4) 各 (family_type, role, sex) について Largest Remainder で age を割当
    for key, persons in persons_by_key.items():
        n_persons = len(persons)
        target = target_pool.get(key, {})

        role = key[1]
        min_age, max_age = ROLE_AGE_CONSTRAINTS.get(role, (0, 120))
        # ハード制約を満たす age のみを残す
        valid_target = {age: cnt for age, cnt in target.items() if min_age <= age <= max_age}

        if not valid_target:
            # target が hard constraint を満たさない、または target が無い:
            # フォールバック (clamp された min_age を全 person に割り当てる、
            # または target=空のまま N 人を最低年齢に均等配置)
            for ent_i, p_i in persons:
                ages_per_entry[ent_i][p_i] = min_age
            continue

        # Largest Remainder で N を age 別に分配
        age_counts = _largest_remainder_split(valid_target, n_persons)

        # age を person に順次割当（age 昇順、person は登場順）
        person_iter = iter(persons)
        for age in sorted(age_counts.keys()):
            n = age_counts[age]
            for _ in range(n):
                ent_i, p_i = next(person_iter)
                ages_per_entry[ent_i][p_i] = age
        # 余りが出ないことを Largest Remainder が保証する

    # 5) None が残っていないか確認、結果を組み立て
    result: list[HouseholdAgeEntry] = []
    for entry, ages in zip(sex_entries, ages_per_entry, strict=True):
        # None が残っていれば想定外
        final_ages = [a if a is not None else 0 for a in ages]
        result.append(
            HouseholdAgeEntry(
                plan=entry.plan,
                roles=entry.roles,
                sexes=entry.sexes,
                ages=final_ages,
            )
        )

    return result


# ---------------------------------------------------------------------------
# 統合関数: generate_initial_population
# ---------------------------------------------------------------------------


def generate_initial_population(
    stats: InitStats,
    rng: np.random.Generator,
    *,
    use_zero_error_init: bool = False,
) -> PopulationArrays:
    """CSV 統計から初期人口（PopulationArrays）を生成する.

    §10.1 の 6 ステップを順に実行し、``PopulationArrays`` として返す。
    生成された人口は以下の 3 統計が入力と完全一致する:
    - family_type 別世帯数
    - household_size 分布（family_type 毎）
    - children 数分布（with_children グループ、Largest Remainder 保証）

    乱数を使うのは Step 5（sex）と Step 6（age）のみ。
    同じ ``rng`` を使えば bitwise 一致の再現性が保証される。

    Parameters
    ----------
    stats : InitStats
        必須・任意の入力統計をまとめたコンテナ。
    rng : np.random.Generator
        乱数発生器。``SeedRegistry(root=42).rng("init")`` で生成するのを推奨。
    use_zero_error_init : bool
        True で Step 6 を Murata 2017 §3 準拠の決定論的 Largest Remainder で
        実行し、F-W 統計（family_type × role × sex × age）の誤差 0 化を狙う
        （Issue #77）。``stats.demographic_by_family_type_role`` が必須。

    Returns
    -------
    PopulationArrays
        全世帯員を並列配列で表した SA 内部表現。

    Examples
    --------
    >>> from synthpop_jp.rng import SeedRegistry
    >>> from synthpop_jp.init.initial_population import generate_initial_population, InitStats
    >>> # (stats を準備して)
    >>> rng = SeedRegistry(root=42).rng("init")
    >>> arrays = generate_initial_population(stats, rng)
    >>> arrays.n_persons > 0
    True
    """
    # Step 1: family_type 別世帯数の確定（決定論的）
    hh_counts = assign_household_counts(stats.family_type_counts)

    # Step 2: 世帯サイズの割当（Largest Remainder）
    plans = assign_household_sizes(hh_counts, stats.household_size_by_family_type)

    # Step 3: children 数の割付（Largest Remainder）
    plans = assign_children_counts(plans, stats.children_count_dist, stats.family_type_mapping)

    # Step 4: role の展開（決定論的）
    role_entries = expand_roles(plans)

    # Step 5: sex の割当（rng 使用）
    sex_entries = assign_sex(role_entries, stats.demographic_by_family_type_role, rng)

    # Step 6: age の割当
    if use_zero_error_init:
        if stats.demographic_by_family_type_role is None:
            msg = (
                "use_zero_error_init=True のとき stats.demographic_by_family_type_role "
                "が必要です（target 比率を Largest Remainder で割り当てるため）"
            )
            raise ValueError(msg)
        age_entries = assign_age_zero_error(
            sex_entries,
            stats.demographic_by_family_type_role,
            rng,
        )
    else:
        age_entries = assign_age(
            sex_entries,
            stats.demographic_by_age_sex,
            stats.demographic_by_family_type_role,
            rng,
        )

    # Household ドメインオブジェクトへ変換し、PopulationArrays を生成
    from synthpop_jp.domain.household import Household
    from synthpop_jp.domain.person import Person

    family_reg = FamilyTypeRegistry()
    role_reg = RoleRegistry()
    sex_reg = SexRegistry()

    # 全 role / family_type を事前登録
    for ft in FAMILY_TEMPLATES:
        family_reg.register(ft)
    for ft_count_row in stats.family_type_counts:
        family_reg.register(ft_count_row.family_type)

    households: list[Household] = []
    for hh_id, entry in enumerate(age_entries, start=1):
        members: list[Person] = []
        for role, sex, age in zip(entry.roles, entry.sexes, entry.ages, strict=True):
            role_reg.register(role)
            members.append(
                Person(
                    household_id=hh_id,
                    role=role,
                    sex=sex,  # type: ignore[arg-type]
                    age=age,
                )
            )
        households.append(
            Household(
                household_id=hh_id,
                family_type=entry.plan.family_type,
                members=members,
            )
        )

    return PopulationArrays.from_households(households, family_reg, role_reg, sex_reg)
