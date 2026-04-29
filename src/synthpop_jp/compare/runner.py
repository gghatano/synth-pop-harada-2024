"""Seed sweep runner (Issue #80).

1 つの config に対し ``n_seeds`` 個の独立 seed で SA を走らせ、各 seed の
``metrics.json`` を集める。

実装方針
--------
- subprocess を起動せず、Python 関数として ``generate`` / ``evaluate`` 相当を
  内部で呼ぶ（高速・テストしやすい）
- 各 seed で ``Settings.seed`` を ``base_seed + i`` に書き換え、
  ``output_dir`` も seed 別の subdir に切り分ける
- 既存の :mod:`synthpop_jp.cli` と同じロジックを再利用するため、
  CLI 用の typer コードを直接呼び出さず、core 関数を呼ぶ形に分離する
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from synthpop_jp.config import Settings


def run_seed_sweep(
    settings: Settings,
    n_seeds: int,
    base_seed: int = 42,
    output_root: Path | None = None,
) -> list[dict[str, float]]:
    """Execute ``settings`` n_seeds 回、各 seed の metrics dict のリストを返す.

    各 seed での流れ:
    1. ``settings.seed = base_seed + i`` で書き換える
    2. ``output_dir = output_root / f"seed_{seed}"`` に切り替え
    3. generate 相当 (合成人口生成) と evaluate 相当 (metrics 計算) を実行
    4. 出力された ``metrics.json`` を読み込んで返す

    Parameters
    ----------
    settings : Settings
        テンプレート設定。``seed`` と ``output_dir`` は本関数が内部で書き換える。
    n_seeds : int
        実行する独立 seed の数（1 以上）。
    base_seed : int
        最初の seed 値。``i`` 番目の seed は ``base_seed + i``。
    output_root : Path | None
        各 seed の出力 subdir の親。``None`` のとき
        ``settings.output_dir / "seeds"`` を使う。

    Returns
    -------
    list[dict[str, float]]
        各 seed の metrics.json をパースした dict のリスト。
    """
    if n_seeds < 1:
        msg = f"n_seeds は 1 以上が必要 (got {n_seeds})"
        raise ValueError(msg)

    import json

    if output_root is None:
        output_root = settings.output_dir / "seeds"
    output_root.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, float]] = []
    for i in range(n_seeds):
        seed = base_seed + i
        seed_output_dir = output_root / f"seed_{seed}"
        seed_settings = settings.model_copy(update={"seed": seed, "output_dir": seed_output_dir})
        _run_one_seed(seed_settings)
        metrics_path = seed_output_dir / "metrics.json"
        if metrics_path.exists():
            raw = json.loads(metrics_path.read_text(encoding="utf-8"))
            metrics_floats: dict[str, float] = {
                k: float(v) for k, v in raw.items() if isinstance(v, (int, float))
            }
            results.append(metrics_floats)
        else:
            results.append({})
    return results


def _run_one_seed(settings: Settings) -> None:
    """1 つの seed で generate + evaluate を実行する.

    typer の CliRunner で同じ Python プロセス内で cli.py のサブコマンドを呼ぶ。
    subprocess 起動を避けることで seed sweep の総実行時間を抑える。
    """
    from typer.testing import CliRunner

    from synthpop_jp.cli import app

    config_path = settings.output_dir / "config.yaml"
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    _write_settings_yaml(settings, config_path)

    runner = CliRunner()
    gen_result = runner.invoke(app, ["generate", "--config", str(config_path)])
    if gen_result.exit_code != 0:
        msg = (
            f"generate failed for seed={settings.seed}: "
            f"exit={gen_result.exit_code}, output={gen_result.output[:500]}"
        )
        raise RuntimeError(msg)

    eval_result = runner.invoke(app, ["evaluate", "--config", str(config_path), "--no-report"])
    if eval_result.exit_code != 0:
        msg = (
            f"evaluate failed for seed={settings.seed}: "
            f"exit={eval_result.exit_code}, output={eval_result.output[:500]}"
        )
        raise RuntimeError(msg)


def _write_settings_yaml(settings: Settings, path: Path) -> None:
    """Dump ``settings`` を YAML 形式で書き出す."""
    import yaml

    data = settings.model_dump(mode="json")
    path.write_text(yaml.dump(data), encoding="utf-8")
