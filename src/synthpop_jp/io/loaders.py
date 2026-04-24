"""CSV ローダ — pydantic v2 ベース、行番号付きバリデーションエラー.

使い方::

    from synthpop_jp.io.loaders import load_family_type_counts, CsvValidationError

    try:
        rows = load_family_type_counts(Path("data/sample_case/family_type_counts.csv"))
    except CsvValidationError as exc:
        print(exc)  # "row 3: ..." のような行番号付きメッセージ

設計方針
--------
- ``pandas.read_csv`` で CSV を読み込み、``to_dict(orient="records")`` でレコードリストに変換する。
- 1 行ずつ ``Model.model_validate(record)`` で検証し、失敗行の番号を
  ``CsvValidationError`` に含める。
- ``family_type_group`` の有効値チェックは ``load_family_type_mapping`` で読んだ YAML を使う。

couple_diff の符号規則
    ``couple_diff = husband_age - wife_age``（夫の年齢 − 妻の年齢）。
    ``data_contract.md`` §4 で確定。ローダ内では符号の反転は行わない。
    入力 CSV が逆符号の場合は前処理スクリプトで反転してから渡す。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from pydantic import BaseModel, ValidationError

from synthpop_jp.io.schemas import (
    AgeDiffCoupleRow,
    AgeDiffParentChildRow,
    ChildrenCountDistRow,
    DemographicByAgeSexRow,
    DemographicByFamilyTypeRoleRow,
    FamilyTypeCountRow,
    HouseholdSizeByFamilyTypeRow,
)

# ---------------------------------------------------------------------------
# エラー型
# ---------------------------------------------------------------------------


class CsvValidationError(Exception):
    """CSV バリデーション失敗時の例外.

    ``row <行番号>: <詳細>`` の形式でメッセージを持つ。
    行番号は 0-indexed（pandas の行番号と一致）。
    """

    def __init__(self, row: int, detail: str) -> None:
        super().__init__(f"row {row}: {detail}")
        self.row = row
        self.detail = detail


# ---------------------------------------------------------------------------
# 内部ユーティリティ
# ---------------------------------------------------------------------------


def _read_csv(path: Path) -> list[dict[str, Any]]:
    """CSV ファイルを読み込み、レコードのリストとして返す."""
    df = pd.read_csv(path)
    return df.to_dict(orient="records")  # type: ignore[return-value]


def _validate_rows[T: BaseModel](
    records: list[dict[str, Any]],
    model: type[T],
) -> list[T]:
    """レコードのリストを pydantic モデルで 1 行ずつ検証する.

    Parameters
    ----------
    records : list[dict[str, Any]]
        CSV から読み込んだレコードのリスト。
    model : type[T]
        検証に使う pydantic モデルクラス（BaseModel のサブクラス）。

    Returns
    -------
    list[T]
        バリデーション済みのモデルインスタンスのリスト。

    Raises
    ------
    CsvValidationError
        いずれかの行がバリデーションに失敗した場合。
    """
    result: list[T] = []
    for i, record in enumerate(records):
        try:
            instance: T = model.model_validate(record)
            result.append(instance)
        except ValidationError as exc:
            # pydantic の ValidationError メッセージを簡略化して行番号付きで返す
            detail = "; ".join(
                f"{'.'.join(str(loc) for loc in e['loc'])}: {e['msg']}" for e in exc.errors()
            )
            raise CsvValidationError(row=i, detail=detail) from exc
    return result


# ---------------------------------------------------------------------------
# family_type_mapping YAML
# ---------------------------------------------------------------------------


def load_family_type_mapping(path: Path) -> dict[str, str]:
    """``configs/family_type_mapping.yaml`` を読み込む.

    Returns
    -------
    dict[str, str]
        ``{family_type: family_type_group}`` の辞書。
    """
    with path.open(encoding="utf-8") as f:
        raw: dict[str, Any] = yaml.safe_load(f)
    # YAML 構造: {family_type: family_type_group, ...}
    return {str(k): str(v) for k, v in raw.items()}


# ---------------------------------------------------------------------------
# 必須 CSV 5 種
# ---------------------------------------------------------------------------


def load_family_type_counts(path: Path) -> list[FamilyTypeCountRow]:
    """family_type_counts.csv をロードする.

    Parameters
    ----------
    path : Path
        CSV ファイルのパス。

    Returns
    -------
    list[FamilyTypeCountRow]
        バリデーション済みの行モデルのリスト。

    Raises
    ------
    CsvValidationError
        型違い・列欠落・値域外の行が含まれる場合。
    """
    records = _read_csv(path)
    return _validate_rows(records, FamilyTypeCountRow)


def load_children_count_dist(
    path: Path,
    *,
    mapping_path: Path | None = None,
) -> list[ChildrenCountDistRow]:
    """children_count_dist.csv をロードする.

    Parameters
    ----------
    path : Path
        CSV ファイルのパス。
    mapping_path : Path | None
        ``family_type_mapping.yaml`` のパス。指定した場合、未登録の
        ``family_type_group`` を含む行があると ``CsvValidationError`` を送出する。

    Returns
    -------
    list[ChildrenCountDistRow]
        バリデーション済みの行モデルのリスト。

    Raises
    ------
    CsvValidationError
        型違い・列欠落・値域外・重複キー・未登録 group の行が含まれる場合。
    """
    records = _read_csv(path)
    rows = _validate_rows(records, ChildrenCountDistRow)

    # 未登録 family_type_group チェック
    if mapping_path is not None:
        mapping = load_family_type_mapping(mapping_path)
        valid_groups = set(mapping.values())
        for i, row in enumerate(rows):
            if row.family_type_group not in valid_groups:
                raise CsvValidationError(
                    row=i,
                    detail=(
                        f"family_type_group '{row.family_type_group}' は"
                        f" '{mapping_path}' に未登録のグループです"
                    ),
                )

    # 重複 (family_type_group, n_children) チェック
    seen: set[tuple[str, int]] = set()
    for i, row in enumerate(rows):
        key = (row.family_type_group, row.n_children)
        if key in seen:
            raise CsvValidationError(
                row=i,
                detail=(
                    f"(family_type_group={row.family_type_group!r},"
                    f" n_children={row.n_children}) が重複しています"
                ),
            )
        seen.add(key)

    return rows


def load_demographic_by_age_sex(path: Path) -> list[DemographicByAgeSexRow]:
    """demographic_by_age_sex.csv をロードする.

    Parameters
    ----------
    path : Path
        CSV ファイルのパス。

    Returns
    -------
    list[DemographicByAgeSexRow]
        バリデーション済みの行モデルのリスト。

    Raises
    ------
    CsvValidationError
        型違い・列欠落・値域外の行が含まれる場合。
    """
    records = _read_csv(path)
    return _validate_rows(records, DemographicByAgeSexRow)


def load_age_diff_parent_child(path: Path) -> list[AgeDiffParentChildRow]:
    """age_diff_parent_child.csv をロードする.

    Parameters
    ----------
    path : Path
        CSV ファイルのパス。

    Returns
    -------
    list[AgeDiffParentChildRow]
        バリデーション済みの行モデルのリスト。

    Raises
    ------
    CsvValidationError
        型違い・列欠落・値域外・diff_min >= diff_max の行が含まれる場合。
    """
    records = _read_csv(path)
    return _validate_rows(records, AgeDiffParentChildRow)


def load_age_diff_couple(path: Path) -> list[AgeDiffCoupleRow]:
    """age_diff_couple.csv をロードする.

    couple_diff の符号規則: ``couple_diff = husband_age - wife_age``。
    夫が年上なら正、妻が年上なら負（``data_contract.md`` §4 参照）。

    Parameters
    ----------
    path : Path
        CSV ファイルのパス。

    Returns
    -------
    list[AgeDiffCoupleRow]
        バリデーション済みの行モデルのリスト。

    Raises
    ------
    CsvValidationError
        型違い・列欠落・diff_min >= diff_max の行が含まれる場合。
    """
    records = _read_csv(path)
    return _validate_rows(records, AgeDiffCoupleRow)


# ---------------------------------------------------------------------------
# 任意 CSV 2 種
# ---------------------------------------------------------------------------


def load_demographic_by_family_type_role(
    path: Path,
) -> list[DemographicByFamilyTypeRoleRow]:
    """demographic_by_family_type_role.csv をロードする（任意入力）.

    Parameters
    ----------
    path : Path
        CSV ファイルのパス。

    Returns
    -------
    list[DemographicByFamilyTypeRoleRow]
        バリデーション済みの行モデルのリスト。

    Raises
    ------
    CsvValidationError
        型違い・列欠落・値域外の行が含まれる場合。
    """
    records = _read_csv(path)
    return _validate_rows(records, DemographicByFamilyTypeRoleRow)


def load_household_size_by_family_type(
    path: Path,
) -> list[HouseholdSizeByFamilyTypeRow]:
    """household_size_by_family_type.csv をロードする（任意入力）.

    Parameters
    ----------
    path : Path
        CSV ファイルのパス。

    Returns
    -------
    list[HouseholdSizeByFamilyTypeRow]
        バリデーション済みの行モデルのリスト。

    Raises
    ------
    CsvValidationError
        型違い・列欠落・値域外の行が含まれる場合。
    """
    records = _read_csv(path)
    return _validate_rows(records, HouseholdSizeByFamilyTypeRow)
