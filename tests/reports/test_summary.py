"""Tests for synthpop_jp.reports.summary module.

非技術者向け要約文生成関数の単体テスト。
固定入力に対して期待される文字列パターンを確認する。
"""

import pandas as pd
import pytest

from synthpop_jp.reports.summary import generate_executive_summary


@pytest.fixture
def sample_metrics() -> dict[str, object]:
    """サンプル metrics.json の内容。"""
    return {
        "total_households": 100,
        "total_persons": 266,
        "family_type_counts": {
            "single": 20,
            "couple": 24,
            "couple_and_children": 30,
            "father_and_children": 3,
            "mother_and_children": 10,
            "couple_and_parents": 2,
            "couple_and_a_parent": 8,
            "couple_children_and_parents": 1,
            "couple_children_and_a_parent": 2,
        },
        "household_size_distribution": {
            "1": 20,
            "2": 28,
            "3": 32,
            "4": 6,
            "5": 14,
        },
    }


@pytest.fixture
def sample_households() -> pd.DataFrame:
    """サンプル世帯データフレーム。"""
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
    """サンプル個人データフレーム。"""
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


class TestGenerateExecutiveSummary:
    """generate_executive_summary 関数のテスト群。"""

    def test_returns_string(
        self,
        sample_metrics: dict[str, object],
        sample_households: pd.DataFrame,
        sample_persons: pd.DataFrame,
    ) -> None:
        """文字列を返すこと。"""
        result = generate_executive_summary(sample_metrics, sample_households, sample_persons)
        assert isinstance(result, str)

    def test_contains_household_count(
        self,
        sample_metrics: dict[str, object],
        sample_households: pd.DataFrame,
        sample_persons: pd.DataFrame,
    ) -> None:
        """世帯数（100）が含まれること。"""
        result = generate_executive_summary(sample_metrics, sample_households, sample_persons)
        assert "100" in result

    def test_contains_person_count(
        self,
        sample_metrics: dict[str, object],
        sample_households: pd.DataFrame,
        sample_persons: pd.DataFrame,
    ) -> None:
        """総人数（266）が含まれること。"""
        result = generate_executive_summary(sample_metrics, sample_households, sample_persons)
        assert "266" in result

    def test_contains_world_sekai_or_setai(
        self,
        sample_metrics: dict[str, object],
        sample_households: pd.DataFrame,
        sample_persons: pd.DataFrame,
    ) -> None:
        """「世帯」という用語が含まれること。"""
        result = generate_executive_summary(sample_metrics, sample_households, sample_persons)
        assert "世帯" in result

    def test_contains_hito_or_nin(
        self,
        sample_metrics: dict[str, object],
        sample_households: pd.DataFrame,
        sample_persons: pd.DataFrame,
    ) -> None:
        """「人」もしくは「名」という用語が含まれること。"""
        result = generate_executive_summary(sample_metrics, sample_households, sample_persons)
        assert "人" in result or "名" in result

    def test_non_empty(
        self,
        sample_metrics: dict[str, object],
        sample_households: pd.DataFrame,
        sample_persons: pd.DataFrame,
    ) -> None:
        """空文字列でないこと。"""
        result = generate_executive_summary(sample_metrics, sample_households, sample_persons)
        assert len(result) > 50

    def test_multiple_sentences(
        self,
        sample_metrics: dict[str, object],
        sample_households: pd.DataFrame,
        sample_persons: pd.DataFrame,
    ) -> None:
        """要約が複数文から構成されること（4〜6 文程度）。"""
        result = generate_executive_summary(sample_metrics, sample_households, sample_persons)
        # 「。」で区切られた文が 3 つ以上あること
        sentences = [s for s in result.split("。") if s.strip()]
        assert len(sentences) >= 3

    def test_no_technical_jargon_without_explanation(
        self,
        sample_metrics: dict[str, object],
        sample_households: pd.DataFrame,
        sample_persons: pd.DataFrame,
    ) -> None:
        """SA という略語単独では登場しないこと（説明なしの専門用語禁止）。"""
        result = generate_executive_summary(sample_metrics, sample_households, sample_persons)
        # "SA" が出てくる場合は括弧補足か説明文が伴うことを確認
        # シンプルに "SA" のみが単独で登場していないことを確認
        assert "（SA）" not in result or "最適化" in result

    def test_uses_metrics_total_households(
        self,
        sample_metrics: dict[str, object],
        sample_households: pd.DataFrame,
        sample_persons: pd.DataFrame,
    ) -> None:
        """metrics の total_households 値（100）を要約に使うこと。"""
        result = generate_executive_summary(sample_metrics, sample_households, sample_persons)
        assert "100" in result

    def test_uses_metrics_total_persons(
        self,
        sample_metrics: dict[str, object],
        sample_households: pd.DataFrame,
        sample_persons: pd.DataFrame,
    ) -> None:
        """metrics の total_persons 値（266）を要約に使うこと。"""
        result = generate_executive_summary(sample_metrics, sample_households, sample_persons)
        assert "266" in result
