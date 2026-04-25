"""HTML report generation module for synthpop-jp.

合成人口の実験結果を、非技術者（経営層・意思決定者）が
ブラウザで直接開ける self-contained HTML として出力する。

公開 API:
    generate_html_report: HTML レポートをファイルに書き出す
    generate_executive_summary: 経営層向け要約文を生成する
    family_type_pie: 家族構成の円グラフを生成する
    population_pyramid: 人口ピラミッドを生成する
    stat_consistency_bar: 統計整合性の棒グラフを生成する
"""

from synthpop_jp.reports.html import generate_html_report
from synthpop_jp.reports.plots import (
    family_type_pie,
    population_pyramid,
    stat_consistency_bar,
)
from synthpop_jp.reports.summary import generate_executive_summary

__all__ = [
    "family_type_pie",
    "generate_executive_summary",
    "generate_html_report",
    "population_pyramid",
    "stat_consistency_bar",
]
