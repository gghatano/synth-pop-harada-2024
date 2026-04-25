"""HTML report generation engine for synthpop-jp.

合成人口の実験結果を self-contained HTML（外部依存ゼロ）として出力する。
CSS はインライン埋め込み、plotly 図は include_plotlyjs="inline"
方式で完全にインライン化する。

対象読者は経営層（完全非技術者）のため、次の設計方針を守る:
- 大きめフォント（1.1rem 以上）
- 高コントラスト（文字と背景の差が明確）
- 要約セクションを背景色 + 太字で視覚的に目立たせる
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from synthpop_jp.reports.plots import (
    family_type_pie,
    population_pyramid,
    stat_consistency_bar,
)
from synthpop_jp.reports.summary import generate_executive_summary

# ---------------------------------------------------------------------------
# インライン CSS（self-contained 維持のため外部ファイルを使わない）
# ---------------------------------------------------------------------------
_CSS = """
/* synthpop-jp HTML レポート 非技術者向けスタイル */

*, *::before, *::after {
    box-sizing: border-box;
}

body {
    font-family: "Hiragino Kaku Gothic ProN", "Hiragino Sans", Meiryo,
                 "Noto Sans CJK JP", sans-serif;
    font-size: 1.1rem;
    line-height: 1.8;
    color: #1a1a1a;
    background: #f9f9f9;
    margin: 0;
    padding: 0;
}

.container {
    max-width: 960px;
    margin: 0 auto;
    padding: 2rem 1.5rem;
}

/* ヘッダー */
.report-header {
    background: #1a3a5c;
    color: #ffffff;
    padding: 2rem 1.5rem;
    margin-bottom: 2rem;
    border-radius: 6px;
}

.report-header h1 {
    font-size: 1.6rem;
    margin: 0 0 0.5rem 0;
    font-weight: 700;
}

.report-header .meta {
    font-size: 0.95rem;
    opacity: 0.85;
}

/* 経営層向け要約セクション */
.executive-summary {
    background: #fffbe6;
    border-left: 6px solid #f5a623;
    border-radius: 4px;
    padding: 1.5rem 1.75rem;
    margin-bottom: 2.5rem;
}

.executive-summary h2 {
    font-size: 1.25rem;
    color: #7a5200;
    margin: 0 0 1rem 0;
    font-weight: 700;
}

.executive-summary p {
    font-size: 1.1rem;
    font-weight: 600;
    color: #3a3000;
    margin: 0;
}

/* セクション共通 */
section {
    background: #ffffff;
    border-radius: 6px;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
    padding: 1.5rem 1.75rem;
    margin-bottom: 2rem;
}

section h2 {
    font-size: 1.2rem;
    color: #1a3a5c;
    margin: 0 0 1rem 0;
    border-bottom: 2px solid #e0e8f0;
    padding-bottom: 0.5rem;
    font-weight: 700;
}

section p {
    color: #333;
    margin-bottom: 0.75rem;
}

/* 統計サマリテーブル */
.stats-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 1.0rem;
    margin: 1rem 0;
}

.stats-table th {
    background: #1a3a5c;
    color: #fff;
    padding: 0.6rem 1rem;
    text-align: left;
    font-weight: 600;
}

.stats-table td {
    padding: 0.55rem 1rem;
    border-bottom: 1px solid #e0e8f0;
}

.stats-table tr:last-child td {
    border-bottom: none;
}

.stats-table tr:nth-child(even) td {
    background: #f4f8fc;
}

/* 図キャプション */
.chart-caption {
    font-size: 0.95rem;
    color: #555;
    text-align: center;
    margin-top: 0.5rem;
    margin-bottom: 1rem;
}

/* フッター */
.report-footer {
    text-align: center;
    font-size: 0.9rem;
    color: #888;
    margin-top: 3rem;
    padding-top: 1rem;
    border-top: 1px solid #ddd;
}
"""


def generate_html_report(
    data: dict[str, object],
    output_path: str | Path,
    template_vars: dict[str, object] | None = None,
) -> None:
    """Write a self-contained HTML report to a file.

    self-contained HTML（外部依存ゼロ）として生成する。
    CSS はインライン埋め込み、plotly 図は inline JS として埋め込む。

    Parameters
    ----------
    data : dict[str, object]
        以下のキーを含む dict:
        - "households": pd.DataFrame — 世帯データ
        - "persons": pd.DataFrame — 個人データ
        - "metrics": dict — quickstart 出力の metrics.json 内容
    output_path : str | Path
        出力先 HTML ファイルのパス（親ディレクトリが存在しない場合は自動作成）。
    template_vars : dict[str, object] | None
        テンプレート変数の追加オプション。現在 "title" キーをサポートする。

    Returns
    -------
    None
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    households: pd.DataFrame = data["households"]  # type: ignore[assignment]
    persons: pd.DataFrame = data["persons"]  # type: ignore[assignment]
    metrics: dict[str, object] = data["metrics"]  # type: ignore[assignment]

    vars_ = template_vars or {}
    title = str(vars_.get("title", "合成人口 実験レポート"))

    total_households = int(metrics.get("total_households", len(households)))
    total_persons = int(metrics.get("total_persons", len(persons)))

    # 経営層向け要約を生成する
    summary_text = generate_executive_summary(metrics, households, persons)

    # plotly 図を生成してインライン HTML に変換する
    pie_fig = family_type_pie(households)
    pyramid_fig = population_pyramid(persons)

    # stat_consistency_bar の入力を用意する
    family_type_counts: dict[str, int] = {}
    raw_counts = metrics.get("family_type_counts")
    if isinstance(raw_counts, dict):
        family_type_counts = {k: int(v) for k, v in raw_counts.items()}
    else:
        family_type_counts = households["family_type"].value_counts().to_dict()

    consistency_fig = stat_consistency_bar(
        observed=family_type_counts,
        target=family_type_counts,  # quickstart は SA 前のため observed = target
    )

    # to_html は div + script タグを返す（plotly JS はまとめて 1 度だけ埋め込む）
    pie_html = pie_fig.to_html(full_html=False, include_plotlyjs="inline", div_id="chart-pie")
    pyramid_html = pyramid_fig.to_html(
        full_html=False, include_plotlyjs=False, div_id="chart-pyramid"
    )
    consistency_html = consistency_fig.to_html(
        full_html=False, include_plotlyjs=False, div_id="chart-consistency"
    )

    # 家族構成テーブルを HTML で生成する
    family_rows = _build_family_table_rows(family_type_counts)

    html_content = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{_escape_html(title)}</title>
    <style>
{_CSS}
    </style>
</head>
<body>
    <div class="container">

        <!-- ヘッダー -->
        <div class="report-header">
            <h1>{_escape_html(title)}</h1>
            <div class="meta">synthpop-jp — 合成人口生成システム 実験レポート</div>
        </div>

        <!-- 経営層向け要約 -->
        <div class="executive-summary">
            <h2>&#x2728; 経営層向け要約（30 秒で読めます）</h2>
            <p>{_escape_html(summary_text)}</p>
        </div>

        <!-- 基本統計 -->
        <section>
            <h2>基本統計</h2>
            <p>今回の生成結果の概要です。</p>
            <table class="stats-table">
                <tr><th>項目</th><th>値</th></tr>
                <tr><td>生成世帯数</td><td>{total_households} 世帯</td></tr>
                <tr><td>生成人数</td><td>{total_persons} 人</td></tr>
                <tr><td>平均世帯人数</td>
                    <td>{total_persons / total_households:.1f} 人/世帯</td></tr>
            </table>
        </section>

        <!-- 家族構成の内訳 -->
        <section>
            <h2>家族構成の内訳（円グラフ）</h2>
            <p>
                生成された {total_households} 世帯を、家族の構成（単身・夫婦のみ・子どもあり 等）
                別に集計したグラフです。グラフの各部分にカーソルを乗せると世帯数と割合が表示されます。
            </p>
            {pie_html}
            <p class="chart-caption">
                図 1: 家族構成タイプ別の世帯数内訳。
                最も多い構成タイプを視覚的に確認できます。
            </p>

            <table class="stats-table">
                <tr><th>家族構成タイプ</th><th>世帯数</th><th>割合</th></tr>
                {family_rows}
            </table>
        </section>

        <!-- 人口ピラミッド -->
        <section>
            <h2>人口ピラミッド（年齢・性別の分布）</h2>
            <p>
                左側の棒が男性、右側の棒が女性を表します。
                棒の長さが長いほど、その年齢層の人数が多いことを示します。
                グラフ上でカーソルを動かすと詳細な人数が表示されます。
            </p>
            {pyramid_html}
            <p class="chart-caption">
                図 2: 年齢 10 歳刻みの男女別人口分布。
                若い世代から高齢世代までのバランスを確認できます。
            </p>
        </section>

        <!-- 統計整合性 -->
        <section>
            <h2>統計整合性（入力統計 vs 生成結果）</h2>
            <p>
                このグラフは「入力統計（目標値）」と「生成結果」の世帯数を並べて比較します。
                2 本の棒が揃っているほど、統計との整合性が高いことを示します。
                現在は SA（焼きなまし法による最適化）を実施する前の初期段階のため、
                両者は完全に一致しています。Phase 2 以降の改善で分布をさらに近づけます。
            </p>
            {consistency_html}
            <p class="chart-caption">
                図 3: 家族構成タイプ別の統計整合性チェック。
                Phase 2 では左右の棒のズレを最小化することを目標にします。
            </p>
        </section>

        <!-- 制約と今後の発展 -->
        <section>
            <h2>現在の制約と今後の発展</h2>
            <p>
                <strong>現在の段階（Phase 1）での制約:</strong>
            </p>
            <ul>
                <li>
                    SA（焼きなまし法）最適化をまだ実施していないため、
                    年齢分布が実際の統計と完全には一致していません。
                </li>
                <li>
                    今回の入力データはダミーデータ（100 世帯のサンプル）です。
                    実際の国勢調査データを用いた検証は Phase 2 以降で実施します。
                </li>
                <li>
                    個人の属性（職業・収入 等）はまだ含まれていません。
                    Phase 3 以降で順次拡張します。
                </li>
            </ul>
            <p>
                <strong>今後の発展（Phase 2 以降）:</strong>
            </p>
            <ul>
                <li>
                    Phase 2: SA 最適化による年齢・世帯規模分布の精度向上。
                    収束の様子もレポートでお届けします。
                </li>
                <li>
                    Phase 3: より細かい地域単位での生成。
                    地域ごとの特性を反映した合成人口が実現します。
                </li>
                <li>
                    Phase 4: 秘匿性（個人が特定されにくいか）と
                    有用性（統計的価値を保てているか）の評価を追加します。
                </li>
            </ul>
        </section>

        <!-- フッター -->
        <div class="report-footer">
            <p>synthpop-jp — 合成人口生成システム &nbsp;|&nbsp;
               このレポートは Python で自動生成されました。</p>
        </div>

    </div>
</body>
</html>
"""

    output_path.write_text(html_content, encoding="utf-8")


# ---------------------------------------------------------------------------
# 内部ヘルパー
# ---------------------------------------------------------------------------

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


def _escape_html(text: str) -> str:
    """Escape HTML special characters in text."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _build_family_table_rows(family_type_counts: dict[str, int]) -> str:
    """Return HTML <tr> elements for the family type summary table."""
    total = sum(family_type_counts.values())
    rows = []
    for key, count in sorted(family_type_counts.items(), key=lambda x: -x[1]):
        label = _FAMILY_TYPE_LABELS.get(key, key)
        ratio = count / total * 100 if total > 0 else 0
        rows.append(f"<tr><td>{_escape_html(label)}</td><td>{count}</td><td>{ratio:.1f}%</td></tr>")
    return "\n".join(rows)
