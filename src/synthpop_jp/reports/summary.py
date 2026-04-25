"""Executive summary generator for non-technical stakeholders.

合成人口の実験結果から、経営層（完全非技術者）が理解できる
要約文を自動生成する。

文体ガイドライン:
- 1 文 40 字以内を目安にする
- 専門用語には括弧補足を付ける
- 「今何が分かったか」と「次に何を決めたいか」の 2 軸で書く
"""

from __future__ import annotations

import pandas as pd


def generate_executive_summary(
    metrics: dict[str, object],
    households: pd.DataFrame,
    persons: pd.DataFrame,
) -> str:
    """Generate an executive summary in Japanese for non-technical readers.

    quickstart の出力データから、非技術者が読んで 30 秒で内容を把握できる
    要約文（日本語）を返す。HTML レポートの冒頭セクションに埋め込んで使う。

    Parameters
    ----------
    metrics : dict[str, object]
        quickstart が出力する metrics.json の内容。
        "total_households"・"total_persons"・"family_type_counts" キーを含む。
    households : pd.DataFrame
        生成された世帯データフレーム（`family_type` 列を含む）。
    persons : pd.DataFrame
        生成された個人データフレーム（`sex`・`age` 列を含む）。

    Returns
    -------
    str
        非技術者向け要約文。複数の文から構成される。
    """
    total_households = int(metrics.get("total_households", len(households)))
    total_persons = int(metrics.get("total_persons", len(persons)))

    # 家族構成の多数派を特定する
    family_type_counts: dict[str, int] = {}
    raw_counts = metrics.get("family_type_counts")
    if isinstance(raw_counts, dict):
        family_type_counts = {k: int(v) for k, v in raw_counts.items()}
    else:
        family_type_counts = households["family_type"].value_counts().to_dict()

    # 最も多い家族構成を日本語に変換する
    _labels = {
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
    top_type_key = max(family_type_counts, key=lambda k: family_type_counts[k])
    top_type_label = _labels.get(top_type_key, top_type_key)
    top_type_count = family_type_counts[top_type_key]
    top_type_ratio = round(top_type_count / total_households * 100)

    # 男女比を算出する
    if "sex" in persons.columns:
        male_count = int((persons["sex"] == "M").sum())
        female_count = int((persons["sex"] == "F").sum())
    else:
        male_count = 0
        female_count = total_persons

    # 要約文を組み立てる（各文は 40 字以内を目標）
    lines = []

    # 第 1 文: 何を生成したか
    lines.append(
        f"合成人口（統計に合わせて人工的に作成した個票データ）を生成しました。"
        f"ダミー入力として {total_households} 世帯を設定し、"
        f"合計 {total_persons} 人分の個人データを出力しました。"
    )

    # 第 2 文: 家族構成の最大構成
    lines.append(
        f"最も多い家族構成は「{top_type_label}」で、"
        f"全 {total_households} 世帯中 {top_type_count} 世帯（{top_type_ratio}%）を占めます。"
    )

    # 第 3 文: 性別構成
    if male_count > 0 or female_count > 0:
        lines.append(f"個人の内訳は男性 {male_count} 人、女性 {female_count} 人です。")

    # 第 4 文: 現フェーズの説明
    lines.append(
        "現在は初期生成（SA 最適化なし）の段階です。"
        "焼きなまし法（SA: 徐々に解を改善する最適化手法）による調整は Phase 2 で実施します。"
    )

    # 第 5 文: 次のアクション
    lines.append(
        "次のステップでは年齢・世帯規模の分布を実データに近づける調整を行います。"
        "その結果も同じ形式のレポートでお届けします。"
    )

    return "".join(lines)
