"""Tests for Table 13 形式 Markdown renderer (Issue #78)."""

from __future__ import annotations

from synthpop_jp.reports.markdown import render_metrics_table13


class TestMinimalAggregateSection:
    """minimal 5 統計の出力."""

    def test_includes_father_child_age_diff(self) -> None:
        metrics: dict[str, float] = {
            "aggregate.l1.father_child_age_diff": 12.0,
            "aggregate.l1.total": 12.0,
        }
        md = render_metrics_table13(metrics)
        assert "father_child_age_diff" in md
        assert "12.0" in md

    def test_total_row_marked(self) -> None:
        """total 行が他の行と区別できる形式（太字）で出る."""
        metrics: dict[str, float] = {
            "aggregate.l1.father_child_age_diff": 12.0,
            "aggregate.l1.total": 45.0,
        }
        md = render_metrics_table13(metrics)
        # total は太字で囲まれているか
        assert "**total**" in md or "**45" in md


class TestExtendedFamilyTypePyramidSection:
    """family_type 別 pyramid を subsection で表示."""

    def test_per_family_type_keys_listed(self) -> None:
        metrics: dict[str, float] = {
            "aggregate.l1.pyramid_per_family_type.couple.M": 5.0,
            "aggregate.l1.pyramid_per_family_type.couple.F": 7.0,
            "aggregate.l1.pyramid_per_family_type.single.M": 3.0,
        }
        md = render_metrics_table13(metrics)
        assert "couple" in md
        assert "single" in md
        # 値も含まれる
        assert "5.0" in md
        assert "7.0" in md
        assert "3.0" in md


class TestRareCellSection:
    """rare cell セクション."""

    def test_global_metrics_present(self) -> None:
        metrics: dict[str, float] = {
            "rare_cell.fraction_below_5": 0.45,
            "rare_cell.fraction_unique": 0.10,
            "rare_cell.total_cells": 200.0,
        }
        md = render_metrics_table13(metrics)
        assert "rare_cell" in md or "rare cell" in md.lower()
        assert "0.45" in md or "0.450" in md or "0.4500" in md

    def test_per_family_type_breakdown_listed(self) -> None:
        metrics: dict[str, float] = {
            "rare_cell.fraction_below_5": 0.45,
            "rare_cell.per_family_type.fraction_below_5.couple": 0.30,
        }
        md = render_metrics_table13(metrics)
        assert "couple" in md


class TestCAPSection:
    """CAP セクションは cap.* キーがあるときだけ出す."""

    def test_cap_section_when_cap_keys_present(self) -> None:
        metrics: dict[str, float] = {
            "cap.generalized": 0.42,
            "cap.targeted": 0.50,
            "cap.coverage": 1.0,
        }
        md = render_metrics_table13(metrics)
        assert "CAP" in md or "cap" in md
        assert "0.42" in md or "0.420" in md or "0.4200" in md

    def test_no_cap_section_when_absent(self) -> None:
        metrics: dict[str, float] = {
            "aggregate.l1.total": 10.0,
        }
        md = render_metrics_table13(metrics)
        # CAP の見出しは出ない（cap キーが無いため）
        assert "## 2.2" not in md or "CAP" not in md.split("## 2.2")[1] if "## 2.2" in md else True


class TestOthersSection:
    """未知キーは「その他」セクションでも切り捨てない."""

    def test_unknown_keys_listed_in_others(self) -> None:
        metrics: dict[str, float] = {
            "aggregate.l1.total": 10.0,
            "plugin_dummy.score": 99.0,
        }
        md = render_metrics_table13(metrics)
        assert "plugin_dummy" in md or "99.0" in md


class TestStructure:
    """全体構造."""

    def test_returns_string(self) -> None:
        md = render_metrics_table13({"aggregate.l1.total": 10.0})
        assert isinstance(md, str)
        assert len(md) > 0

    def test_starts_with_h1_title(self) -> None:
        md = render_metrics_table13({"aggregate.l1.total": 10.0})
        assert md.startswith("# ")
