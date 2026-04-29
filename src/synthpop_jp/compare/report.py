"""compare.json / compare.md の出力 (Issue #80)."""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any


def render_compare_json(
    config_paths: list[Path],
    n_seeds: int,
    metric_keys: list[str],
    results_per_config: list[list[dict[str, float]]],
    test_results: dict[str, dict[str, dict[str, float]]],
    holm_alpha: float = 0.05,
    holm_rejected: list[bool] | None = None,
    ci_per_metric: dict[str, dict[str, tuple[float, float]]] | None = None,
) -> str:
    """compare.json の文字列を生成.

    Parameters
    ----------
    config_paths : list[Path]
        比較した config のパス一覧。
    n_seeds : int
        各 config を実行した seed 数。
    metric_keys : list[str]
        統計検定対象の metric キー。
    results_per_config : list[list[dict[str, float]]]
        ``results_per_config[i][j]`` は ``config_paths[i]`` の ``j`` 番目 seed の metrics。
    test_results : dict[str, dict[str, dict[str, float]]]
        ``test_results[metric][test_name] = {"statistic": ..., "p_value": ...}``
        ``test_name`` は ``"welch_t"`` / ``"wilcoxon"``。
    holm_alpha : float
        多重比較補正の α。
    holm_rejected : list[bool] | None
        各 metric の welch p に対する Holm 補正後の棄却フラグ。
    ci_per_metric : dict[str, dict[str, tuple[float, float]]] | None
        ``ci_per_metric[metric][config_path] = (ci_low, ci_high)``（Issue #81）。
    """
    payload: dict[str, Any] = {
        "configs": [str(p) for p in config_paths],
        "n_seeds": n_seeds,
        "metrics": {},
    }
    for metric in metric_keys:
        per_config: dict[str, dict[str, Any]] = {}
        for i, cfg in enumerate(config_paths):
            values = [r.get(metric, float("nan")) for r in results_per_config[i]]
            entry: dict[str, Any] = {
                "mean": _safe_mean(values),
                "std": _safe_std(values),
                "values": values,
            }
            if ci_per_metric is not None:
                ci = ci_per_metric.get(metric, {}).get(str(cfg))
                if ci is not None:
                    entry["ci_low"] = ci[0]
                    entry["ci_high"] = ci[1]
            per_config[str(cfg)] = entry
        payload["metrics"][metric] = {
            "per_config": per_config,
            "tests": test_results.get(metric, {}),
        }
    if holm_rejected is not None:
        payload["holm_corrected"] = {
            "alpha": holm_alpha,
            "rejected_per_metric": dict(zip(metric_keys, holm_rejected, strict=True)),
        }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def render_compare_md(
    config_paths: list[Path],
    n_seeds: int,
    metric_keys: list[str],
    results_per_config: list[list[dict[str, float]]],
    test_results: dict[str, dict[str, dict[str, float]]],
    holm_rejected: list[bool] | None = None,
    ci_per_metric: dict[str, dict[str, tuple[float, float]]] | None = None,
) -> str:
    """compare.md の文字列を生成 (Harada 2024 Table 13 風).

    ``ci_per_metric`` が渡されたとき、各セルに ``mean [ci_low, ci_high]`` の
    形式で 95% CI も併記する（Issue #81）。
    """
    lines: list[str] = ["# 比較レポート (Issue #80)", ""]
    lines.append(f"- **configs**: {len(config_paths)}")
    for i, p in enumerate(config_paths):
        lines.append(f"  - config_{i}: `{p}`")
    lines.append(f"- **n_seeds**: {n_seeds}")
    lines.append("")

    lines.append("## 指標別の平均と検定結果")
    lines.append("")
    header = ["metric"]
    for i in range(len(config_paths)):
        header.append(f"config_{i} mean ± std")
    header.extend(["welch_t p", "wilcoxon p", "Holm rejected"])
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["---"] * len(header)) + "|")
    for j, metric in enumerate(metric_keys):
        row = [metric]
        for i, cfg in enumerate(config_paths):
            values = [r.get(metric, float("nan")) for r in results_per_config[i]]
            mean = _safe_mean(values)
            std = _safe_std(values)
            cell = f"{mean:.3f} ± {std:.3f}"
            if ci_per_metric is not None:
                ci = ci_per_metric.get(metric, {}).get(str(cfg))
                if ci is not None:
                    cell += f" [{ci[0]:.3f}, {ci[1]:.3f}]"
            row.append(cell)
        tests = test_results.get(metric, {})
        welch_p = tests.get("welch_t", {}).get("p_value", float("nan"))
        wilcoxon_p = tests.get("wilcoxon", {}).get("p_value", float("nan"))
        row.append(f"{welch_p:.4f}")
        row.append(f"{wilcoxon_p:.4f}")
        if holm_rejected is not None:
            row.append("✓" if holm_rejected[j] else "")
        else:
            row.append("")
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")
    return "\n".join(lines) + "\n"


def _safe_mean(values: list[float]) -> float:
    finite = [v for v in values if not _is_nan(v)]
    return statistics.mean(finite) if finite else float("nan")


def _safe_std(values: list[float]) -> float:
    finite = [v for v in values if not _is_nan(v)]
    return statistics.stdev(finite) if len(finite) > 1 else 0.0


def _is_nan(v: float) -> bool:
    return v != v  # NaN check (NaN != NaN)
