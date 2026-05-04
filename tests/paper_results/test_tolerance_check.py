"""Unit tests for paper_results._shared.tolerance_check (Issue #115 Step 1).

`tolerance_check.compare(actual_csv, expected_csv, tol_score, tol_utility)` は
expected と actual の CSV を行ごと・列ごとに突き合わせ、相対差分が許容幅を超える
セルを報告する。`best_score` 系の列は ``tol_score``（既定 0.01 = ±1%）、
``utility`` を名前に含む列は ``tol_utility``（既定 0.05 = ±5%）で判定する。

NaN ポリシー: expected と actual の両方が NaN なら一致扱い。一方だけ NaN は
不一致。これは決定論性を担保するため意図的に PASS させる。
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
from paper_results._shared.tolerance_check import Report, compare

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_csv(path: Path, header: list[str], rows: list[list[object]]) -> None:
    """Write a small CSV file used by these tests."""
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            w.writerow(r)


# ---------------------------------------------------------------------------
# Equality / boundary tests
# ---------------------------------------------------------------------------


def test_compare_passes_on_exact_match(tmp_path: Path) -> None:
    """完全一致のときは passed=True で violations が空."""
    expected = tmp_path / "expected.csv"
    actual = tmp_path / "actual.csv"
    _write_csv(expected, ["seed", "transition", "best_score"], [[1, "age_change", 100.0]])
    _write_csv(actual, ["seed", "transition", "best_score"], [[1, "age_change", 100.0]])

    report = compare(actual, expected)

    assert isinstance(report, Report)
    assert report.passed is True
    assert report.violations == []


def test_compare_passes_on_within_score_tolerance(tmp_path: Path) -> None:
    """+0.5% は ±1% の許容内なので PASS."""
    expected = tmp_path / "expected.csv"
    actual = tmp_path / "actual.csv"
    _write_csv(expected, ["seed", "best_score"], [[1, 100.0]])
    _write_csv(actual, ["seed", "best_score"], [[1, 100.5]])

    report = compare(actual, expected, tol_score=0.01, tol_utility=0.05)

    assert report.passed is True


def test_compare_fails_on_score_violation(tmp_path: Path) -> None:
    """+1.5% は ±1% を超えるので FAIL し、行・列・差分率が報告に出る."""
    expected = tmp_path / "expected.csv"
    actual = tmp_path / "actual.csv"
    _write_csv(
        expected,
        ["seed", "transition", "best_score"],
        [[1, "age_change", 100.0], [2, "age_change", 200.0]],
    )
    _write_csv(
        actual,
        ["seed", "transition", "best_score"],
        [[1, "age_change", 101.5], [2, "age_change", 200.0]],
    )

    report = compare(actual, expected, tol_score=0.01, tol_utility=0.05)

    assert report.passed is False
    assert len(report.violations) == 1
    v = report.violations[0]
    assert v.row_index == 0
    assert v.column == "best_score"
    assert v.actual == pytest.approx(101.5)
    assert v.expected == pytest.approx(100.0)
    assert v.relative_diff == pytest.approx(0.015, rel=1e-6)
    assert v.tolerance == pytest.approx(0.01)


def test_compare_uses_utility_tolerance_for_utility_columns(tmp_path: Path) -> None:
    """``utility`` を名前に含む列は ±5% まで PASS."""
    expected = tmp_path / "expected.csv"
    actual = tmp_path / "actual.csv"
    _write_csv(expected, ["seed", "narrow_utility"], [[1, 0.80]])
    _write_csv(actual, ["seed", "narrow_utility"], [[1, 0.832]])  # +4%

    report = compare(actual, expected, tol_score=0.01, tol_utility=0.05)

    assert report.passed is True


def test_compare_fails_on_utility_violation(tmp_path: Path) -> None:
    """utility 列でも +6% は ±5% を超えて FAIL."""
    expected = tmp_path / "expected.csv"
    actual = tmp_path / "actual.csv"
    _write_csv(expected, ["seed", "broad_utility"], [[1, 0.50]])
    _write_csv(actual, ["seed", "broad_utility"], [[1, 0.53]])  # +6%

    report = compare(actual, expected, tol_score=0.01, tol_utility=0.05)

    assert report.passed is False
    assert len(report.violations) == 1
    assert report.violations[0].column == "broad_utility"
    assert report.violations[0].tolerance == pytest.approx(0.05)


def test_compare_fails_on_row_count_mismatch(tmp_path: Path) -> None:
    """行数が違えば FAIL（structural violation として 1 件報告）."""
    expected = tmp_path / "expected.csv"
    actual = tmp_path / "actual.csv"
    _write_csv(expected, ["seed", "best_score"], [[1, 100.0], [2, 200.0]])
    _write_csv(actual, ["seed", "best_score"], [[1, 100.0]])

    report = compare(actual, expected)

    assert report.passed is False
    assert any("row count" in v.message.lower() for v in report.violations)


def test_compare_fails_on_column_mismatch(tmp_path: Path) -> None:
    """列名が違えば FAIL."""
    expected = tmp_path / "expected.csv"
    actual = tmp_path / "actual.csv"
    _write_csv(expected, ["seed", "best_score"], [[1, 100.0]])
    _write_csv(actual, ["seed", "score"], [[1, 100.0]])

    report = compare(actual, expected)

    assert report.passed is False
    assert any("column" in v.message.lower() for v in report.violations)


def test_compare_treats_both_nan_as_match(tmp_path: Path) -> None:
    """expected も actual も NaN なら PASS（決定論性ポリシー）."""
    expected = tmp_path / "expected.csv"
    actual = tmp_path / "actual.csv"
    _write_csv(expected, ["seed", "best_score"], [[1, "nan"]])
    _write_csv(actual, ["seed", "best_score"], [[1, "nan"]])

    report = compare(actual, expected)

    assert report.passed is True


def test_compare_fails_when_only_one_side_is_nan(tmp_path: Path) -> None:
    """片側だけ NaN なら FAIL."""
    expected = tmp_path / "expected.csv"
    actual = tmp_path / "actual.csv"
    _write_csv(expected, ["seed", "best_score"], [[1, "nan"]])
    _write_csv(actual, ["seed", "best_score"], [[1, 100.0]])

    report = compare(actual, expected)

    assert report.passed is False


def test_compare_handles_zero_expected(tmp_path: Path) -> None:
    """expected が 0 のとき、actual も 0 なら PASS、非 0 なら FAIL."""
    expected = tmp_path / "expected.csv"
    actual = tmp_path / "actual.csv"
    _write_csv(expected, ["seed", "best_score"], [[1, 0.0], [2, 0.0]])
    _write_csv(actual, ["seed", "best_score"], [[1, 0.0], [2, 1.0]])

    report = compare(actual, expected)

    assert report.passed is False
    assert len(report.violations) == 1
    assert report.violations[0].row_index == 1


def test_compare_ignores_string_columns(tmp_path: Path) -> None:
    """文字列列（seed や transition のような ID/category）は数値比較しない."""
    expected = tmp_path / "expected.csv"
    actual = tmp_path / "actual.csv"
    _write_csv(
        expected,
        ["seed", "transition", "best_score"],
        [[1, "age_change", 100.0]],
    )
    _write_csv(
        actual,
        ["seed", "transition", "best_score"],
        [[1, "age_change", 100.0]],
    )

    report = compare(actual, expected)

    assert report.passed is True


def test_report_to_markdown_lists_violations() -> None:
    """Markdown 出力に行番号・列名・差分率が含まれる（CI summary 用）."""
    from paper_results._shared.tolerance_check import Violation

    report = Report(
        passed=False,
        violations=[
            Violation(
                row_index=2,
                column="best_score",
                expected=100.0,
                actual=102.0,
                relative_diff=0.02,
                tolerance=0.01,
                message="best_score relative diff 2.0% exceeds tolerance 1.0%",
            )
        ],
    )

    md = report.to_markdown()

    assert "best_score" in md
    assert "row 2" in md or "row=2" in md.replace(" ", "")
    assert "2.0%" in md or "0.02" in md
