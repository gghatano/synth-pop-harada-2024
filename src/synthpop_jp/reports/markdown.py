"""Table 13 形式の Markdown renderer (Issue #78).

`synthpop-jp evaluate` が出力する flat な ``metrics.json`` を、
Harada 2024 Table 13 形式の人間に読みやすい Markdown に整形する。

セクション構成
--------------
1. **統計整合性** (``aggregate.l1.*``)
   - 1.1 minimal 5 統計
   - 1.2 family_type × sex pyramid (拡張モード時のみ)
2. **秘匿性**
   - 2.1 rare cell (proxy 指標)
   - 2.2 CAP / TCAP (attribute inference、``--real-persons-csv`` 指定時のみ)
3. **その他** (entry_points プラグイン等の未分類キー)

全セクションが空のときは空の Markdown を返さず、最低限のヘッダだけ出す。
"""

from __future__ import annotations

from collections import defaultdict


def _format_value(v: float) -> str:
    """Metric 値の表示形式を統一する.

    - 0.0–1.0 の比率らしき値: 4 桁
    - それ以外: 小数 1 桁
    """
    if 0.0 <= v <= 1.0 and v != int(v):
        return f"{v:.4f}"
    return f"{v:.1f}"


def _render_minimal_aggregate(rows: dict[str, float]) -> list[str]:
    """Minimal 5 統計と total を Markdown table で返す."""
    lines: list[str] = []
    if not rows:
        return lines
    lines.append("### 1.1 minimal 5 統計")
    lines.append("")
    lines.append("| 統計 | L1 誤差 |")
    lines.append("|---|---:|")
    # total は最後に
    items = sorted([(k, v) for k, v in rows.items() if k != "total"])
    for k, v in items:
        lines.append(f"| {k} | {_format_value(v)} |")
    if "total" in rows:
        lines.append(f"| **total** | **{_format_value(rows['total'])}** |")
    lines.append("")
    return lines


def _render_family_type_pyramid(rows: dict[str, dict[str, float]]) -> list[str]:
    """family_type × sex の pyramid L1 を 2 列 table で返す.

    ``rows`` は ``{family_type: {"M": l1, "F": l1}}`` の dict。
    """
    lines: list[str] = []
    if not rows:
        return lines
    lines.append("### 1.2 family_type 別 demographic pyramid")
    lines.append("")
    lines.append("| family_type | M | F |")
    lines.append("|---|---:|---:|")
    for ft in sorted(rows.keys()):
        m = rows[ft].get("M", 0.0)
        f = rows[ft].get("F", 0.0)
        lines.append(f"| {ft} | {_format_value(m)} | {_format_value(f)} |")
    lines.append("")
    return lines


def _render_rare_cell(
    global_rows: dict[str, float], per_ft: dict[str, dict[str, float]]
) -> list[str]:
    lines: list[str] = []
    if not global_rows and not per_ft:
        return lines
    lines.append("### 2.1 rare cell (proxy)")
    lines.append("")
    if global_rows:
        lines.append("| 指標 | 値 |")
        lines.append("|---|---:|")
        for k in sorted(global_rows.keys()):
            lines.append(f"| {k} | {_format_value(global_rows[k])} |")
        lines.append("")
    if per_ft:
        lines.append("**family_type 別 (fraction_below_5 / fraction_unique):**")
        lines.append("")
        lines.append("| family_type | fraction_below_5 | fraction_unique |")
        lines.append("|---|---:|---:|")
        for ft in sorted(per_ft.keys()):
            sub = per_ft[ft]
            lines.append(
                f"| {ft} | {_format_value(sub.get('fraction_below_5', 0.0))} | "
                f"{_format_value(sub.get('fraction_unique', 0.0))} |"
            )
        lines.append("")
    return lines


def _render_cap(global_rows: dict[str, float], per_ft: dict[str, dict[str, float]]) -> list[str]:
    lines: list[str] = []
    if not global_rows and not per_ft:
        return lines
    lines.append("### 2.2 CAP / TCAP (attribute inference)")
    lines.append("")
    if global_rows:
        lines.append("| 指標 | 値 |")
        lines.append("|---|---:|")
        for k in sorted(global_rows.keys()):
            lines.append(f"| {k} | {_format_value(global_rows[k])} |")
        lines.append("")
    if per_ft:
        lines.append("**family_type 別 (generalized / targeted):**")
        lines.append("")
        lines.append("| family_type | generalized | targeted |")
        lines.append("|---|---:|---:|")
        for ft in sorted(per_ft.keys()):
            sub = per_ft[ft]
            lines.append(
                f"| {ft} | {_format_value(sub.get('generalized', 0.0))} | "
                f"{_format_value(sub.get('targeted', 0.0))} |"
            )
        lines.append("")
    return lines


def _render_broad_utility(
    univariate: dict[str, dict[str, float]],
    pair_tv: dict[str, float],
    scalars: dict[str, float],
) -> list[str]:
    """Broad utility セクションを Markdown で組み立てる (Issue #96).

    ``univariate`` は ``{attr: {"tv": ..., "l1": ...}}``、
    ``pair_tv`` は ``{"a__b": value}``、
    ``scalars`` は ``{"sum_pair_tv": ..., "correlation_frobenius_diff": ...,
    "correlation_max_abs_diff": ...}`` を期待する。
    """
    lines: list[str] = []
    if not (univariate or pair_tv or scalars):
        return lines
    lines.append("## 3. 有用性: broad utility")
    lines.append("")
    if univariate:
        lines.append("### 単変量 TV / L1")
        lines.append("")
        lines.append("| 属性 | TV | L1 |")
        lines.append("|---|---:|---:|")
        for attr in sorted(univariate.keys()):
            row = univariate[attr]
            tv = _format_value(row.get("tv", 0.0))
            l1 = _format_value(row.get("l1", 0.0))
            lines.append(f"| {attr} | {tv} | {l1} |")
        lines.append("")
    if pair_tv:
        lines.append("### 属性ペア joint TV")
        lines.append("")
        lines.append("| ペア | joint TV |")
        lines.append("|---|---:|")
        for k in sorted(pair_tv.keys()):
            lines.append(f"| {k} | {_format_value(pair_tv[k])} |")
        lines.append("")
    if scalars:
        lines.append("### スカラ要約")
        lines.append("")
        lines.append("| 指標 | 値 |")
        lines.append("|---|---:|")
        for k in sorted(scalars.keys()):
            lines.append(f"| {k} | {_format_value(scalars[k])} |")
        lines.append("")
    return lines


def _render_others(rows: dict[str, float]) -> list[str]:
    lines: list[str] = []
    if not rows:
        return lines
    lines.append("## 4. その他 / プラグイン")
    lines.append("")
    lines.append("| キー | 値 |")
    lines.append("|---|---:|")
    for k in sorted(rows.keys()):
        lines.append(f"| {k} | {_format_value(rows[k])} |")
    lines.append("")
    return lines


def render_metrics_table13(metrics: dict[str, float]) -> str:
    """Metrics dict を Harada 2024 Table 13 形式の Markdown に変換する.

    Parameters
    ----------
    metrics : dict[str, float]
        ``synthpop-jp evaluate`` が ``metrics.json`` に書き出すキー一式。

    Returns
    -------
    str
        Markdown 文字列。空の metrics でも最低限のヘッダを返す。
    """
    # キーをグループ分け
    aggregate_minimal: dict[str, float] = {}
    pyramid_per_ft: dict[str, dict[str, float]] = defaultdict(dict)
    rare_cell_global: dict[str, float] = {}
    rare_cell_per_ft: dict[str, dict[str, float]] = defaultdict(dict)
    cap_global: dict[str, float] = {}
    cap_per_ft: dict[str, dict[str, float]] = defaultdict(dict)
    broad_univariate: dict[str, dict[str, float]] = defaultdict(dict)
    broad_pair_tv: dict[str, float] = {}
    broad_scalars: dict[str, float] = {}
    others: dict[str, float] = {}

    for key, value in metrics.items():
        if key.startswith("aggregate.l1.pyramid_per_family_type."):
            # aggregate.l1.pyramid_per_family_type.<ft>.<sex>
            tail = key.removeprefix("aggregate.l1.pyramid_per_family_type.")
            parts = tail.rsplit(".", 1)
            if len(parts) == 2:
                ft, sex = parts
                pyramid_per_ft[ft][sex] = float(value)
            else:
                others[key] = float(value)
        elif key.startswith("aggregate.l1."):
            # minimal 5 + total
            stat = key.removeprefix("aggregate.l1.")
            aggregate_minimal[stat] = float(value)
        elif key.startswith("rare_cell.per_family_type."):
            # rare_cell.per_family_type.<metric>.<ft>
            tail = key.removeprefix("rare_cell.per_family_type.")
            parts = tail.split(".", 1)
            if len(parts) == 2:
                metric, ft = parts
                rare_cell_per_ft[ft][metric] = float(value)
            else:
                others[key] = float(value)
        elif key.startswith("rare_cell."):
            metric = key.removeprefix("rare_cell.")
            rare_cell_global[metric] = float(value)
        elif key.startswith("cap.per_family_type."):
            tail = key.removeprefix("cap.per_family_type.")
            parts = tail.split(".", 1)
            if len(parts) == 2:
                metric, ft = parts
                cap_per_ft[ft][metric] = float(value)
            else:
                others[key] = float(value)
        elif key.startswith("cap."):
            metric = key.removeprefix("cap.")
            cap_global[metric] = float(value)
        elif key.startswith("broad_utility.tv."):
            attr = key.removeprefix("broad_utility.tv.")
            broad_univariate[attr]["tv"] = float(value)
        elif key.startswith("broad_utility.l1."):
            attr = key.removeprefix("broad_utility.l1.")
            broad_univariate[attr]["l1"] = float(value)
        elif key.startswith("broad_utility.pair_tv."):
            pair_key = key.removeprefix("broad_utility.pair_tv.")
            broad_pair_tv[pair_key] = float(value)
        elif key.startswith("broad_utility."):
            scalar_key = key.removeprefix("broad_utility.")
            broad_scalars[scalar_key] = float(value)
        else:
            others[key] = float(value)

    lines: list[str] = ["# 評価レポート (Table 13 形式)", ""]

    # 1. 統計整合性
    if aggregate_minimal or pyramid_per_ft:
        lines.append("## 1. 統計整合性 (aggregate L1)")
        lines.append("")
        lines.extend(_render_minimal_aggregate(aggregate_minimal))
        lines.extend(_render_family_type_pyramid(pyramid_per_ft))

    # 2. 秘匿性
    if rare_cell_global or rare_cell_per_ft or cap_global or cap_per_ft:
        lines.append("## 2. 秘匿性")
        lines.append("")
        lines.extend(_render_rare_cell(rare_cell_global, rare_cell_per_ft))
        lines.extend(_render_cap(cap_global, cap_per_ft))

    # 3. 有用性 broad utility (Issue #96)
    lines.extend(_render_broad_utility(dict(broad_univariate), broad_pair_tv, broad_scalars))

    # 4. その他
    if others:
        lines.extend(_render_others(others))

    return "\n".join(lines) + "\n"
