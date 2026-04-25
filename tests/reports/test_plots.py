"""Tests for synthpop_jp.reports.plots module.

各 plotly 図ヘルパー関数の単体テスト。
Figure オブジェクトの型・トレース数・主要プロパティを確認する。
"""

import pandas as pd
import plotly.graph_objects as go
import pytest

from synthpop_jp.reports.plots import (
    family_type_pie,
    population_pyramid,
    stat_consistency_bar,
)


@pytest.fixture
def sample_households() -> pd.DataFrame:
    """サンプル世帯データ。"""
    return pd.DataFrame(
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


@pytest.fixture
def sample_persons() -> pd.DataFrame:
    """サンプル個人データ（男女・年齢あり）。"""
    rows = []
    for i in range(20):
        rows.append(
            {
                "person_id": f"P_{i:03d}",
                "household_id": f"HH_{i // 2:03d}",
                "family_type": "single" if i < 4 else "couple",
                "role": "single" if i < 4 else "husband",
                "sex": "M" if i % 2 == 0 else "F",
                "age": 20 + i * 2,
            }
        )
    return pd.DataFrame(rows)


class TestFamilyTypePie:
    """family_type_pie 関数のテスト群。"""

    def test_returns_figure(self, sample_households: pd.DataFrame) -> None:
        """plotly.graph_objects.Figure を返すこと。"""
        fig = family_type_pie(sample_households)
        assert isinstance(fig, go.Figure)

    def test_has_one_trace(self, sample_households: pd.DataFrame) -> None:
        """円グラフは 1 本のトレースを持つこと。"""
        fig = family_type_pie(sample_households)
        assert len(fig.data) == 1

    def test_trace_is_pie(self, sample_households: pd.DataFrame) -> None:
        """トレースが Pie 型であること。"""
        fig = family_type_pie(sample_households)
        assert isinstance(fig.data[0], go.Pie)

    def test_labels_contain_family_types(self, sample_households: pd.DataFrame) -> None:
        """ラベルに family_type の数と同数のエントリが含まれること。"""
        fig = family_type_pie(sample_households)
        pie_trace = fig.data[0]
        expected_count = sample_households["family_type"].nunique()
        assert len(pie_trace.labels) == expected_count

    def test_values_sum_to_total_households(self, sample_households: pd.DataFrame) -> None:
        """値の合計が世帯数と一致すること。"""
        fig = family_type_pie(sample_households)
        pie_trace = fig.data[0]
        assert sum(pie_trace.values) == len(sample_households)

    def test_has_title(self, sample_households: pd.DataFrame) -> None:
        """タイトルが設定されていること。"""
        fig = family_type_pie(sample_households)
        assert fig.layout.title.text is not None
        assert len(fig.layout.title.text) > 0


class TestPopulationPyramid:
    """population_pyramid 関数のテスト群。"""

    def test_returns_figure(self, sample_persons: pd.DataFrame) -> None:
        """plotly.graph_objects.Figure を返すこと。"""
        fig = population_pyramid(sample_persons)
        assert isinstance(fig, go.Figure)

    def test_has_two_traces(self, sample_persons: pd.DataFrame) -> None:
        """男女それぞれ 1 本ずつ、計 2 本のトレースを持つこと。"""
        fig = population_pyramid(sample_persons)
        assert len(fig.data) == 2

    def test_traces_are_bar(self, sample_persons: pd.DataFrame) -> None:
        """トレースが Bar 型であること。"""
        fig = population_pyramid(sample_persons)
        for trace in fig.data:
            assert isinstance(trace, go.Bar)

    def test_trace_names_contain_sex(self, sample_persons: pd.DataFrame) -> None:
        """トレース名に性別（男性/女性）が含まれること。"""
        fig = population_pyramid(sample_persons)
        names = {trace.name for trace in fig.data}
        # 男性と女性の両方を表す名前が存在すること
        assert len(names) == 2

    def test_has_title(self, sample_persons: pd.DataFrame) -> None:
        """タイトルが設定されていること。"""
        fig = population_pyramid(sample_persons)
        assert fig.layout.title.text is not None
        assert len(fig.layout.title.text) > 0

    def test_total_count_matches(self, sample_persons: pd.DataFrame) -> None:
        """全トレースの値の総和が総人口と一致すること。"""
        fig = population_pyramid(sample_persons)
        total = sum(abs(v) for trace in fig.data for v in trace.x)
        assert total == len(sample_persons)


class TestStatConsistencyBar:
    """stat_consistency_bar 関数のテスト群。"""

    def test_returns_figure(self) -> None:
        """plotly.graph_objects.Figure を返すこと。"""
        observed = {"single": 20, "couple": 24, "couple_and_children": 30}
        target = {"single": 18, "couple": 25, "couple_and_children": 32}
        fig = stat_consistency_bar(observed, target)
        assert isinstance(fig, go.Figure)

    def test_has_two_traces(self) -> None:
        """入力統計と生成結果の 2 本のトレースを持つこと。"""
        observed = {"single": 20, "couple": 24}
        target = {"single": 18, "couple": 25}
        fig = stat_consistency_bar(observed, target)
        assert len(fig.data) == 2

    def test_traces_are_bar(self) -> None:
        """トレースが Bar 型であること。"""
        observed = {"single": 20, "couple": 24}
        target = {"single": 18, "couple": 25}
        fig = stat_consistency_bar(observed, target)
        for trace in fig.data:
            assert isinstance(trace, go.Bar)

    def test_categories_are_consistent(self) -> None:
        """両トレースのカテゴリ（x 値）が一致すること。"""
        observed = {"single": 20, "couple": 24, "couple_and_children": 30}
        target = {"single": 18, "couple": 25, "couple_and_children": 32}
        fig = stat_consistency_bar(observed, target)
        x_sets = [set(trace.x) for trace in fig.data]
        assert x_sets[0] == x_sets[1]

    def test_has_title(self) -> None:
        """タイトルが設定されていること。"""
        observed = {"single": 20}
        target = {"single": 18}
        fig = stat_consistency_bar(observed, target)
        assert fig.layout.title.text is not None
        assert len(fig.layout.title.text) > 0
