"""plotly figure helpers for HTML reports.

合成人口の実験結果を可視化する plotly Figure を返す関数群。
生成された Figure は HTML レポートにインライン埋め込みする前提で設計している。

対象読者は経営層（完全非技術者）のため、図のラベル・タイトルは日本語で記述し、
専門用語には補足を添える。
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

# 家族構成タイプの日本語ラベル対応表
_FAMILY_TYPE_LABELS: dict[str, str] = {
    "single": "単身世帯",
    "couple": "夫婦のみ",
    "couple_and_children": "夫婦と子ども",
    "father_and_children": "父子世帯",
    "mother_and_children": "母子世帯",
    "couple_and_parents": "夫婦と親（両側）",
    "couple_and_a_parent": "夫婦と親（片側）",
    "couple_children_and_parents": "夫婦・子ども・親（両側）",
    "couple_children_and_a_parent": "夫婦・子ども・親（片側）",
}

# 性別の日本語ラベル
_SEX_LABELS: dict[str, str] = {
    "M": "男性",
    "F": "女性",
}

# 経営層向けカラーパレット（高コントラスト、柔らかい色調）
_COLORS_PIE = [
    "#4E79A7",
    "#F28E2B",
    "#59A14F",
    "#E15759",
    "#76B7B2",
    "#EDC948",
    "#B07AA1",
    "#FF9DA7",
    "#9C755F",
]

_COLOR_MALE = "#4E79A7"  # 青系
_COLOR_FEMALE = "#E15759"  # 赤系
_COLOR_OBSERVED = "#4E79A7"  # 生成結果
_COLOR_TARGET = "#F28E2B"  # 入力統計


def family_type_pie(households: pd.DataFrame) -> go.Figure:
    """Return a pie chart showing household counts by family type.

    ホバー時に各家族構成の世帯数と割合が表示される。

    Parameters
    ----------
    households : pd.DataFrame
        `family_type` 列を含む世帯データフレーム。

    Returns
    -------
    go.Figure
        plotly の円グラフ Figure。
    """
    counts = households["family_type"].value_counts()

    labels = [_FAMILY_TYPE_LABELS.get(ft, ft) for ft in counts.index]
    values = counts.to_numpy().tolist()

    trace = go.Pie(
        labels=labels,
        values=values,
        hovertemplate="<b>%{label}</b><br>世帯数: %{value}<br>割合: %{percent}<extra></extra>",
        textinfo="label+percent",
        textposition="inside",
        marker={"colors": _COLORS_PIE[: len(labels)]},
    )

    fig = go.Figure(data=[trace])
    fig.update_layout(
        title={
            "text": "家族構成別 世帯数の内訳",
            "font": {"size": 18},
            "x": 0.5,
            "xanchor": "center",
        },
        font={"size": 13},
        margin={"t": 80, "b": 20, "l": 20, "r": 20},
        showlegend=True,
        legend={
            "title": "家族構成タイプ",
            "orientation": "v",
            "x": 1.0,
            "xanchor": "left",
        },
    )

    return fig


def population_pyramid(persons: pd.DataFrame) -> go.Figure:
    """Return a population pyramid chart grouped by sex and age band.

    左右対称の棒グラフで、左が男性・右が女性を表す。
    ホバー時に年齢層と人数が表示される。

    Parameters
    ----------
    persons : pd.DataFrame
        `sex`（"M"/"F"）・`age` 列を含む個人データフレーム。

    Returns
    -------
    go.Figure
        plotly の左右棒グラフ Figure。
    """
    # 年齢を 10 歳刻みのビンに区切る
    age_bins = list(range(0, 81, 10))
    age_labels = [f"{a}〜{a + 9}歳" for a in age_bins[:-1]]
    age_labels.append("80歳以上")

    # Issue #53: persons.copy() で全行を二重に持つのを避けるため、
    # age_group は Series 単体で計算し、value_counts で集約する。
    age_group = pd.cut(
        persons["age"],
        bins=[*age_bins, 200],
        labels=age_labels,
        right=False,
    )
    male_mask = persons["sex"] == "M"
    female_mask = persons["sex"] == "F"

    male_counts = age_group[male_mask].value_counts()
    female_counts = age_group[female_mask].value_counts()

    # 全年齢層を揃える
    all_groups = pd.CategoricalIndex(age_labels)
    male_counts = male_counts.reindex(all_groups, fill_value=0)
    female_counts = female_counts.reindex(all_groups, fill_value=0)

    # 男性は負値にして左側に表示する
    male_x = [-v for v in male_counts.to_numpy()]

    male_trace = go.Bar(
        name=_SEX_LABELS["M"],
        y=age_labels,
        x=male_x,
        orientation="h",
        marker={"color": _COLOR_MALE, "opacity": 0.85},
        hovertemplate="<b>男性 %{y}</b><br>人数: %{customdata}<extra></extra>",
        customdata=male_counts.to_numpy(),
    )

    female_trace = go.Bar(
        name=_SEX_LABELS["F"],
        y=age_labels,
        x=female_counts.to_numpy(),
        orientation="h",
        marker={"color": _COLOR_FEMALE, "opacity": 0.85},
        hovertemplate="<b>女性 %{y}</b><br>人数: %{x}<extra></extra>",
    )

    fig = go.Figure(data=[male_trace, female_trace])
    fig.update_layout(
        title={
            "text": "人口ピラミッド（男女別・年齢層別）",
            "font": {"size": 18},
            "x": 0.5,
            "xanchor": "center",
        },
        barmode="relative",
        font={"size": 13},
        xaxis={
            "title": "人数（左: 男性 / 右: 女性）",
            "tickvals": [],
            "showticklabels": False,
        },
        yaxis={"title": "年齢層"},
        legend={
            "orientation": "h",
            "x": 0.5,
            "xanchor": "center",
            "y": -0.1,
        },
        margin={"t": 80, "b": 80, "l": 100, "r": 40},
    )

    return fig


def stat_consistency_bar(
    observed: dict[str, int | float],
    target: dict[str, int | float],
) -> go.Figure:
    """Return a grouped bar chart comparing observed and target distributions.

    2 本の棒グラフを横並びで表示し、入力統計との整合性を視覚的に確認できる。

    Parameters
    ----------
    observed : dict[str, int | float]
        生成結果のカテゴリ別カウント。
    target : dict[str, int | float]
        入力統計のカテゴリ別カウント。

    Returns
    -------
    go.Figure
        plotly の並置棒グラフ Figure。
    """
    # 全カテゴリを揃える（observed と target の union）
    all_categories = sorted(set(observed) | set(target))
    labels = [_FAMILY_TYPE_LABELS.get(c, c) for c in all_categories]

    obs_values = [observed.get(c, 0) for c in all_categories]
    tgt_values = [target.get(c, 0) for c in all_categories]

    observed_trace = go.Bar(
        name="生成結果",
        x=labels,
        y=obs_values,
        marker={"color": _COLOR_OBSERVED, "opacity": 0.85},
        hovertemplate="<b>生成結果</b><br>%{x}: %{y} 世帯<extra></extra>",
    )

    target_trace = go.Bar(
        name="入力統計（目標値）",
        x=labels,
        y=tgt_values,
        marker={"color": _COLOR_TARGET, "opacity": 0.85},
        hovertemplate="<b>入力統計</b><br>%{x}: %{y} 世帯<extra></extra>",
    )

    fig = go.Figure(data=[observed_trace, target_trace])
    fig.update_layout(
        title={
            "text": "統計整合性: 入力統計 vs 生成結果",
            "font": {"size": 18},
            "x": 0.5,
            "xanchor": "center",
        },
        barmode="group",
        font={"size": 13},
        xaxis={"title": "家族構成タイプ", "tickangle": -30},
        yaxis={"title": "世帯数"},
        legend={
            "orientation": "h",
            "x": 0.5,
            "xanchor": "center",
            "y": -0.2,
        },
        margin={"t": 80, "b": 120, "l": 60, "r": 40},
    )

    return fig
