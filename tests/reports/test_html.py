"""Tests for synthpop_jp.reports.html module.

HTML レポート生成エンジンの単体テスト。
生成ファイルの存在確認・主要タグ含有・plotly inline JS の埋め込みを確認する。
"""

import re
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from synthpop_jp.reports.html import generate_html_report


@pytest.fixture
def sample_data() -> dict[str, object]:
    """サンプルレポートデータ。"""
    households = pd.DataFrame(
        {
            "household_id": [f"HH_{i:03d}" for i in range(10)],
            "family_type": [
                "single",
                "single",
                "couple",
                "couple",
                "couple_and_children",
                "couple_and_children",
                "couple_and_children",
                "mother_and_children",
                "father_and_children",
                "couple_and_parents",
            ],
            "household_size": [1, 1, 2, 2, 3, 4, 3, 3, 3, 4],
        }
    )

    persons_rows = []
    for i in range(20):
        persons_rows.append(
            {
                "person_id": f"P_{i:03d}",
                "household_id": f"HH_{i // 2:03d}",
                "family_type": "single" if i < 4 else "couple",
                "role": "single" if i < 4 else "husband",
                "sex": "M" if i % 2 == 0 else "F",
                "age": 20 + i * 2,
            }
        )
    persons = pd.DataFrame(persons_rows)

    metrics = {
        "total_households": 10,
        "total_persons": 20,
        "family_type_counts": {
            "single": 2,
            "couple": 2,
            "couple_and_children": 3,
            "mother_and_children": 1,
            "father_and_children": 1,
            "couple_and_parents": 1,
        },
        "household_size_distribution": {"1": 2, "2": 4, "3": 3, "4": 1},
    }

    return {
        "households": households,
        "persons": persons,
        "metrics": metrics,
    }


class TestGenerateHtmlReport:
    """generate_html_report 関数のテスト群。"""

    def test_creates_output_file(self, sample_data: dict[str, object]) -> None:
        """出力 HTML ファイルが生成されること。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.html"
            generate_html_report(sample_data, output_path)
            assert output_path.exists()

    def test_file_is_not_empty(self, sample_data: dict[str, object]) -> None:
        """出力ファイルが空でないこと。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.html"
            generate_html_report(sample_data, output_path)
            assert output_path.stat().st_size > 0

    def test_output_is_valid_html(self, sample_data: dict[str, object]) -> None:
        """出力が HTML 構造を持つこと（<!DOCTYPE html> タグあり）。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.html"
            generate_html_report(sample_data, output_path)
            content = output_path.read_text(encoding="utf-8")
            assert "<!DOCTYPE html>" in content or "<!doctype html>" in content.lower()

    def test_has_html_body_tags(self, sample_data: dict[str, object]) -> None:
        """<html>・<head>・<body> タグを含むこと。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.html"
            generate_html_report(sample_data, output_path)
            content = output_path.read_text(encoding="utf-8")
            assert "<html" in content
            assert "<head" in content
            assert "<body" in content

    def test_contains_plotly_inline_js(self, sample_data: dict[str, object]) -> None:
        """plotly の JavaScript がインライン埋め込みされていること（外部 CDN 不要）。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.html"
            generate_html_report(sample_data, output_path)
            content = output_path.read_text(encoding="utf-8")
            # plotly の inline JS には "Plotly" という文字列が含まれる
            assert "Plotly" in content

    def test_contains_executive_summary_section(self, sample_data: dict[str, object]) -> None:
        """経営層向け要約セクションが含まれること。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.html"
            generate_html_report(sample_data, output_path)
            content = output_path.read_text(encoding="utf-8")
            assert "要約" in content or "summary" in content.lower()

    def test_contains_household_data(self, sample_data: dict[str, object]) -> None:
        """世帯数が HTML 内に含まれること。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.html"
            generate_html_report(sample_data, output_path)
            content = output_path.read_text(encoding="utf-8")
            assert "世帯" in content

    def test_contains_persons_data(self, sample_data: dict[str, object]) -> None:
        """個人数が HTML 内に含まれること。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.html"
            generate_html_report(sample_data, output_path)
            content = output_path.read_text(encoding="utf-8")
            assert "人" in content

    def test_contains_inline_css(self, sample_data: dict[str, object]) -> None:
        """インライン CSS（<style> タグ）が含まれること（外部 CSS ファイル不要）。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.html"
            generate_html_report(sample_data, output_path)
            content = output_path.read_text(encoding="utf-8")
            assert "<style" in content

    def test_no_external_css_links(self, sample_data: dict[str, object]) -> None:
        """外部 CSS ファイルへのリンクが含まれないこと（self-contained の保証）。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.html"
            generate_html_report(sample_data, output_path)
            content = output_path.read_text(encoding="utf-8")
            # rel="stylesheet" の外部リンクがないこと
            external_css = re.findall(
                r'<link[^>]+rel=["\']stylesheet["\'][^>]+href=["\']https?://', content
            )
            assert len(external_css) == 0

    def test_file_size_under_5mb(self, sample_data: dict[str, object]) -> None:
        """ファイルサイズが 5MB 以下であること（plotly inline 含む）。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.html"
            generate_html_report(sample_data, output_path)
            size_mb = output_path.stat().st_size / (1024 * 1024)
            assert size_mb < 5.0

    def test_accepts_string_path(self, sample_data: dict[str, object]) -> None:
        """output_path に文字列を渡せること。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = str(Path(tmpdir) / "report.html")
            generate_html_report(sample_data, output_path)
            assert Path(output_path).exists()

    def test_template_vars_title_used(self, sample_data: dict[str, object]) -> None:
        """template_vars の title がタイトルに反映されること。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.html"
            title = "テスト実験レポート2026"
            generate_html_report(sample_data, output_path, template_vars={"title": title})
            content = output_path.read_text(encoding="utf-8")
            assert title in content

    def test_returns_none(self, sample_data: dict[str, object]) -> None:
        """戻り値が None であること。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.html"
            result = generate_html_report(sample_data, output_path)
            assert result is None

    def test_creates_parent_directory_if_not_exists(self, sample_data: dict[str, object]) -> None:
        """出力先ディレクトリが存在しない場合に自動作成すること。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "nested" / "dir" / "report.html"
            generate_html_report(sample_data, output_path)
            assert output_path.exists()

    def test_json_metrics_input_also_works(self) -> None:
        """metrics を dict として直接渡しても正常動作すること。"""
        metrics = {
            "total_households": 5,
            "total_persons": 10,
            "family_type_counts": {"single": 3, "couple": 2},
            "household_size_distribution": {"1": 3, "2": 2},
        }
        households = pd.DataFrame(
            {
                "household_id": [f"HH_{i}" for i in range(5)],
                "family_type": ["single", "single", "single", "couple", "couple"],
                "household_size": [1, 1, 1, 2, 2],
            }
        )
        persons = pd.DataFrame(
            {
                "person_id": [f"P_{i}" for i in range(10)],
                "household_id": [f"HH_{i // 2}" for i in range(10)],
                "family_type": ["single"] * 6 + ["couple"] * 4,
                "role": ["single"] * 6 + ["husband"] * 4,
                "sex": ["M", "F"] * 5,
                "age": list(range(20, 70, 5)),
            }
        )
        data = {"households": households, "persons": persons, "metrics": metrics}

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.html"
            generate_html_report(data, output_path)
            assert output_path.exists()
