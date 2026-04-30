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


class TestCitationSection:
    """出典セクション（Issue #101）."""

    def test_aggregate_keys_yield_murata_citation(self) -> None:
        metrics: dict[str, float] = {"aggregate.l1.total": 12.0}
        md = render_metrics_table13(metrics)
        assert "出典" in md or "citations" in md.lower()
        assert "Murata 2017" in md

    def test_cap_keys_yield_taub_citation(self) -> None:
        metrics: dict[str, float] = {"cap.generalized": 0.4}
        md = render_metrics_table13(metrics)
        assert "Taub" in md or "Differential Correct Attribution" in md

    def test_broad_utility_keys_yield_harada_citation(self) -> None:
        metrics: dict[str, float] = {
            "broad_utility.correlation_frobenius_diff": 1.0,
        }
        md = render_metrics_table13(metrics)
        assert "Harada 2024" in md
        assert "Cramér" in md or "dython" in md

    def test_narrow_utility_keys_yield_esteban_citation(self) -> None:
        metrics: dict[str, float] = {
            "narrow_utility.task_a.tstr_macro_f1": 0.85,
        }
        md = render_metrics_table13(metrics)
        assert "TSTR" in md or "Esteban" in md or "Harada 2024" in md


class TestLicenseSection:
    """ライセンスセクション（Issue #101）."""

    def test_default_license_section(self) -> None:
        metrics: dict[str, float] = {"aggregate.l1.total": 1.0}
        md = render_metrics_table13(metrics)
        assert "ライセンス" in md
        assert "Apache-2.0" in md

    def test_estat_provenance_yields_estat_attribution(self) -> None:
        metrics: dict[str, float] = {"aggregate.l1.total": 1.0}
        provenance: dict[str, object] = {
            "data_source": "e-stat",
            "source_url": "https://www.e-stat.go.jp/...",
            "retrieved_at": "2026-04-30",
        }
        md = render_metrics_table13(metrics, provenance=provenance)
        assert "e-Stat" in md
        assert "統計法 §44" in md or "出典表示" in md
        assert "2026-04-30" in md

    def test_provenance_none_default(self) -> None:
        # provenance なしでも壊れない
        md = render_metrics_table13({"aggregate.l1.total": 1.0})
        assert "Apache-2.0" in md


class TestBroadUtilitySection:
    """broad utility セクション（Issue #96）."""

    def test_univariate_table_present(self) -> None:
        metrics: dict[str, float] = {
            "broad_utility.tv.age": 0.25,
            "broad_utility.l1.age": 0.50,
            "broad_utility.tv.sex": 0.10,
            "broad_utility.l1.sex": 0.20,
        }
        md = render_metrics_table13(metrics)
        assert "broad utility" in md
        assert "age" in md
        assert "sex" in md
        # TV / L1 の値が含まれる
        assert "0.25" in md or "0.3" in md  # 値の四捨五入差を許容

    def test_pair_tv_table_present(self) -> None:
        metrics: dict[str, float] = {
            "broad_utility.pair_tv.age__sex": 0.33,
            "broad_utility.pair_tv.age__role": 0.44,
        }
        md = render_metrics_table13(metrics)
        assert "age__sex" in md
        assert "age__role" in md

    def test_correlation_scalars_present(self) -> None:
        metrics: dict[str, float] = {
            "broad_utility.correlation_frobenius_diff": 1.23,
            "broad_utility.correlation_max_abs_diff": 0.55,
            "broad_utility.sum_pair_tv": 1.10,
        }
        md = render_metrics_table13(metrics)
        assert "correlation_frobenius_diff" in md
        assert "correlation_max_abs_diff" in md
        assert "sum_pair_tv" in md

    def test_broad_utility_section_skipped_when_empty(self) -> None:
        # broad_utility キーが無いとセクション自体が出ない
        md = render_metrics_table13({"aggregate.l1.total": 1.0})
        assert "broad utility" not in md.lower() or "## 3. 有用性" not in md


class TestStructure:
    """全体構造."""

    def test_returns_string(self) -> None:
        md = render_metrics_table13({"aggregate.l1.total": 10.0})
        assert isinstance(md, str)
        assert len(md) > 0

    def test_starts_with_h1_title(self) -> None:
        md = render_metrics_table13({"aggregate.l1.total": 10.0})
        assert md.startswith("# ")
