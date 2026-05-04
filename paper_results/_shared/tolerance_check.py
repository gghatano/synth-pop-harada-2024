"""Tolerance comparator for paper_results experiments (Issue #115 Step 1).

`compare(actual_csv, expected_csv, tol_score, tol_utility)` は expected と actual
の CSV を 1 行ずつ突き合わせ、相対差分が許容幅を超えるセルを ``Report`` として
返す。CI から呼ぶための CLI も同梱する。

Tolerance policy
----------------
- `best_score` 系の数値列: ``tol_score``（既定 0.01 = ±1%, spec §19.4 一次根拠）
- 列名に ``utility`` を含む数値列: ``tol_utility``（既定 0.05 = ±5%）
- 文字列列（seed や transition のような ID/category）は文字列一致でチェック
- expected が 0 のときは絶対差で判定（``abs(actual) <= tol_score``）

NaN policy
----------
- 両方 NaN なら一致扱い（決定論性を担保するため意図的に PASS）
- 片側だけ NaN なら不一致（FAIL）

CLI
---
``python -m paper_results._shared.tolerance_check <actual> <expected>`` で
exit 0 (PASS) / exit 1 (FAIL) を返す。``--markdown`` で Markdown 出力。
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

#: best_score 系の数値列に適用する既定許容幅（相対 1%, spec §19.4）。
DEFAULT_TOL_SCORE = 0.01

#: utility 系の数値列に適用する既定許容幅（相対 5%）。
DEFAULT_TOL_UTILITY = 0.05


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Violation:
    """1 件の許容幅違反.

    Attributes
    ----------
    row_index : int
        actual / expected で揃っている 0-indexed 行番号。構造的な違反
        （行数・列名）の場合は -1 を入れる。
    column : str
        違反が起きた列名。構造的違反のときは空文字列。
    expected : float
        期待値。``None`` 相当は ``math.nan``。
    actual : float
        実測値。``None`` 相当は ``math.nan``。
    relative_diff : float
        ``abs(actual - expected) / abs(expected)``。expected==0 のときは
        ``abs(actual)``（絶対差）を入れる。構造的違反では math.nan。
    tolerance : float
        この列に適用された許容幅。構造的違反では math.nan。
    message : str
        人間向けの 1 行説明。
    """

    row_index: int
    column: str
    expected: float
    actual: float
    relative_diff: float
    tolerance: float
    message: str


@dataclass
class Report:
    """compare の戻り値.

    Attributes
    ----------
    passed : bool
        全セルが許容幅内なら True。
    violations : list[Violation]
        違反のリスト。passed=True なら空。
    """

    passed: bool
    violations: list[Violation] = field(default_factory=lambda: [])

    def to_markdown(self) -> str:
        """CI summary 用の Markdown 表現を返す.

        Returns
        -------
        str
            ``$GITHUB_STEP_SUMMARY`` に流せるサマリ文字列。
        """
        if self.passed:
            return "## Tolerance check: PASS\n\nAll values within tolerance.\n"
        lines = [
            "## Tolerance check: FAIL",
            "",
            f"{len(self.violations)} violation(s) found.",
            "",
            "| row | column | expected | actual | rel diff | tolerance | message |",
            "|---:|---|---:|---:|---:|---:|---|",
        ]
        for v in self.violations:
            rel = "n/a" if math.isnan(v.relative_diff) else f"{v.relative_diff * 100:.2f}%"
            tol = "n/a" if math.isnan(v.tolerance) else f"{v.tolerance * 100:.1f}%"
            exp_str = "nan" if math.isnan(v.expected) else f"{v.expected:.6g}"
            act_str = "nan" if math.isnan(v.actual) else f"{v.actual:.6g}"
            row_str = f"row {v.row_index}" if v.row_index >= 0 else "-"
            col_str = v.column or "-"
            lines.append(
                f"| {row_str} | {col_str} | {exp_str} | {act_str} | {rel} | {tol} | {v.message} |"
            )
        lines.append("")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _read_rows(path: Path) -> tuple[list[str], list[list[str]]]:
    """CSV を ``(header, rows)`` で返す."""
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)
    if not rows:
        return [], []
    header = rows[0]
    body = rows[1:]
    return header, body


def _parse_float(s: str) -> float | None:
    """文字列を float に変換。失敗したら None（=文字列カテゴリ列）."""
    s_stripped = s.strip()
    if s_stripped == "":
        return math.nan
    try:
        return float(s_stripped)
    except ValueError:
        return None


def _select_tolerance(column: str, tol_score: float, tol_utility: float) -> float:
    """列名に応じて適用する許容幅を返す."""
    return tol_utility if "utility" in column.lower() else tol_score


def _compare_cell(
    expected_raw: str,
    actual_raw: str,
    *,
    row_index: int,
    column: str,
    tolerance: float,
) -> Violation | None:
    """1 セルを比較して違反があれば Violation を返す."""
    expected = _parse_float(expected_raw)
    actual = _parse_float(actual_raw)

    # どちらかが文字列カテゴリ → 文字列一致を要求
    if expected is None or actual is None:
        if expected_raw.strip() == actual_raw.strip():
            return None
        return Violation(
            row_index=row_index,
            column=column,
            expected=math.nan,
            actual=math.nan,
            relative_diff=math.nan,
            tolerance=tolerance,
            message=(
                f"string mismatch in column '{column}': "
                f"expected={expected_raw!r}, actual={actual_raw!r}"
            ),
        )

    # NaN policy: 両方 NaN なら一致、片側 NaN なら不一致
    e_nan = math.isnan(expected)
    a_nan = math.isnan(actual)
    if e_nan and a_nan:
        return None
    if e_nan ^ a_nan:
        return Violation(
            row_index=row_index,
            column=column,
            expected=expected,
            actual=actual,
            relative_diff=math.nan,
            tolerance=tolerance,
            message=f"NaN mismatch in column '{column}'",
        )

    # 数値比較
    if expected == 0.0:
        diff = abs(actual)
        rel = diff  # treated as absolute when expected==0
    else:
        rel = abs(actual - expected) / abs(expected)

    if rel <= tolerance:
        return None
    return Violation(
        row_index=row_index,
        column=column,
        expected=expected,
        actual=actual,
        relative_diff=rel,
        tolerance=tolerance,
        message=(
            f"{column} relative diff {rel * 100:.2f}% exceeds tolerance {tolerance * 100:.1f}%"
        ),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compare(
    actual_csv: Path,
    expected_csv: Path,
    *,
    tol_score: float = DEFAULT_TOL_SCORE,
    tol_utility: float = DEFAULT_TOL_UTILITY,
) -> Report:
    """expected_csv と actual_csv を許容幅判定で比較する.

    Parameters
    ----------
    actual_csv : Path
        実測値 CSV のパス（``run.py`` が書き出したもの）。
    expected_csv : Path
        期待値 CSV のパス（``expected/`` 配下）。
    tol_score : float
        best_score 系列に適用する相対許容幅（既定 0.01 = ±1%）。
    tol_utility : float
        ``utility`` を名前に含む列に適用する相対許容幅（既定 0.05 = ±5%）。

    Returns
    -------
    Report
        ``passed`` と違反リストを含む結果オブジェクト。
    """
    expected_header, expected_rows = _read_rows(expected_csv)
    actual_header, actual_rows = _read_rows(actual_csv)

    violations: list[Violation] = []

    # 構造チェック: 列名
    if expected_header != actual_header:
        violations.append(
            Violation(
                row_index=-1,
                column="",
                expected=math.nan,
                actual=math.nan,
                relative_diff=math.nan,
                tolerance=math.nan,
                message=(
                    f"column header mismatch: expected={expected_header}, actual={actual_header}"
                ),
            )
        )
        return Report(passed=False, violations=violations)

    # 構造チェック: 行数
    if len(expected_rows) != len(actual_rows):
        violations.append(
            Violation(
                row_index=-1,
                column="",
                expected=math.nan,
                actual=math.nan,
                relative_diff=math.nan,
                tolerance=math.nan,
                message=(
                    f"row count mismatch: expected={len(expected_rows)}, actual={len(actual_rows)}"
                ),
            )
        )
        return Report(passed=False, violations=violations)

    # セル比較
    for i, (e_row, a_row) in enumerate(zip(expected_rows, actual_rows, strict=True)):
        for col_idx, column in enumerate(expected_header):
            tol = _select_tolerance(column, tol_score, tol_utility)
            v = _compare_cell(
                e_row[col_idx],
                a_row[col_idx],
                row_index=i,
                column=column,
                tolerance=tol,
            )
            if v is not None:
                violations.append(v)

    return Report(passed=not violations, violations=violations)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """CLI entry: ``python -m paper_results._shared.tolerance_check ...``.

    Parameters
    ----------
    argv : list[str] | None
        コマンドライン引数。``None`` のとき ``sys.argv[1:]`` を使う。

    Returns
    -------
    int
        exit code (0=PASS, 1=FAIL, 2=usage error)。
    """
    parser = argparse.ArgumentParser(
        prog="paper_results.tolerance_check",
        description="Compare actual_csv and expected_csv by relative tolerance.",
    )
    parser.add_argument("actual", type=Path, help="actual CSV path")
    parser.add_argument("expected", type=Path, help="expected CSV path")
    parser.add_argument(
        "--tol-score",
        type=float,
        default=DEFAULT_TOL_SCORE,
        help="relative tolerance for best_score columns (default 0.01)",
    )
    parser.add_argument(
        "--tol-utility",
        type=float,
        default=DEFAULT_TOL_UTILITY,
        help="relative tolerance for utility columns (default 0.05)",
    )
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="emit Markdown summary instead of plain text",
    )
    parser.add_argument(
        "--summary-out",
        type=Path,
        default=None,
        help="optional path to also write the Markdown summary (e.g. $GITHUB_STEP_SUMMARY)",
    )
    args = parser.parse_args(argv)

    report = compare(
        actual_csv=args.actual,
        expected_csv=args.expected,
        tol_score=args.tol_score,
        tol_utility=args.tol_utility,
    )
    md = report.to_markdown()
    if args.markdown:
        sys.stdout.write(md)
    else:
        if report.passed:
            sys.stdout.write("PASS: all values within tolerance\n")
        else:
            sys.stdout.write(f"FAIL: {len(report.violations)} violation(s)\n")
            for v in report.violations:
                sys.stdout.write(f"  - {v.message}\n")
    if args.summary_out is not None:
        args.summary_out.parent.mkdir(parents=True, exist_ok=True)
        with args.summary_out.open("a", encoding="utf-8") as f:
            f.write(md)

    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
