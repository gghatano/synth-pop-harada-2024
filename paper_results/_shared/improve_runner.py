"""Improve loop runner wrapper for paper_results (Issue #121, Step 1).

experiment-03（戦略比較）と experiment-04（複数候補ばらつき）の両方が呼ぶ
共通ラッパ。``synthpop_jp.improve.runner.run_improve_loop`` を 1 戦略 × 1 seed
で叩き、各 trial の 3 目的代理 metrics を ``pandas.DataFrame`` にまとめて返す。

決定性
------
``base_config_path`` × ``strategy_name`` × ``seed`` × ``n_trials`` を固定すれば、
``best_score`` 列が bitwise 一致する（spec §19.3）。

3 目的 metrics の定義
---------------------
- ``statistical_fit`` = ``aggregate.l1.total``（21 統計の L1 合計）
- ``utility_proxy`` = ``best_score / initial_score``（小さいほど良い）
- ``privacy_proxy`` = ``rare_cell.unique_rate``（小さいほど良い）
- ``composite`` = (statistical_fit_norm + utility_proxy + privacy_proxy) / 3
  （statistical_fit はトリオ内 max で割って [0, 1] に正規化）

``composite`` は本 paper_results 用の暫定平均で、experiment-03 / 04 の
``report.md`` で「将来見直し可能性あり」と明記する。
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, cast

import pandas as pd

from synthpop_jp.config import Settings
from synthpop_jp.improve.runner import StrategyName, run_improve_loop

if TYPE_CHECKING:
    from synthpop_jp.improve.runner import TrialResult

REPO_ROOT = Path(__file__).resolve().parents[2]


def _resolve_input_dir(base_config_path: Path, settings: Settings) -> Path:
    """``settings.input_dir`` を絶対パスに正規化する.

    YAML の ``input_dir`` は **相対パス（リポジトリ root 起点）** でも書ける
    ようにする。配布版で paper_results/ から呼ばれるときに毎回 cwd 依存に
    なるのを避けたい。
    """
    raw = settings.input_dir
    if raw.is_absolute():
        return raw
    # 1) base_config_path の親（configs/）と合わせる
    candidate = (base_config_path.parent / raw).resolve()
    if candidate.exists():
        return candidate
    # 2) リポジトリ root と合わせる
    candidate2 = (REPO_ROOT / raw).resolve()
    return candidate2


def _trial_to_row(
    *,
    seed: int,
    strategy_name: str,
    tr: TrialResult,
) -> dict[str, float | int | str]:
    """1 trial の TrialResult を 3 目的 metrics の dict に変換する."""
    m = tr.metrics
    return {
        "seed": int(seed),
        "strategy": str(strategy_name),
        "trial_id": int(tr.trial_id),
        "best_score": float(m.get("best_score", float("nan"))),
        "initial_score": float(m.get("initial_score", float("nan"))),
        # 3 目的代理（runner._run_one_trial が computed 済みのキーを優先）
        "statistical_fit": float(m.get("statistical_fit", float("nan"))),
        "utility_proxy": float(m.get("utility", float("nan"))),
        "privacy_proxy": float(m.get("privacy", float("nan"))),
        "elapsed_s": float(tr.elapsed_s),
    }


def _attach_composite(df: pd.DataFrame) -> pd.DataFrame:
    """``composite`` 列を計算して付与する.

    DataFrame 内で statistical_fit を [0, 1] に正規化（max で割る）し、
    utility_proxy / privacy_proxy はそのまま使って 3 軸平均を計算する。
    値が NaN や全行同値のときは安全側の代替（statistical_fit/最大=1.0）を使う。
    """
    if df.empty:
        df["composite"] = []
        return df

    sf_max = float(df["statistical_fit"].max())
    if sf_max <= 0.0 or pd.isna(sf_max):
        sf_norm = pd.Series(1.0, index=df.index)
    else:
        sf_norm = df["statistical_fit"] / sf_max
    composite = (sf_norm + df["utility_proxy"] + df["privacy_proxy"]) / 3.0
    df = df.copy()
    df["composite"] = composite.astype(float)
    return df


def run_improve_for_paper_results(
    *,
    base_config_path: Path,
    strategy_name: str,
    n_trials: int,
    seed: int,
    output_root: Path,
    n_households: int | None = None,
) -> pd.DataFrame:
    """1 戦略 × 1 seed × n_trials の improve loop を回し metrics を DataFrame で返す.

    Parameters
    ----------
    base_config_path : Path
        base settings の YAML（``configs/improve_quick.yaml`` を想定）。
    strategy_name : str
        ``"rule_based"`` / ``"pareto"`` / ``"random_search"`` のいずれか。
    n_trials : int
        試行数（1 以上）。
    seed : int
        SA / 戦略の root seed。
    output_root : Path
        improve loop 出力ルート（``output_root/<strategy>_seed<seed>/`` 以下）。
    n_households : int | None
        フル設定時の世帯数（100 の倍数）。``None`` または既定の 100 のときは
        ``base_config_path`` の ``input_dir`` を素直に使う。100 以外を渡した
        ときは ``data/sample_case/`` を整数倍スケールして tmp に書き出し、
        improve loop の入力を差し替える。

    Returns
    -------
    pandas.DataFrame
        列: ``seed``, ``strategy``, ``trial_id``, ``best_score``,
        ``initial_score``, ``statistical_fit``, ``utility_proxy``,
        ``privacy_proxy``, ``elapsed_s``, ``composite``。
    """
    if n_trials < 1:
        msg = f"n_trials は 1 以上が必要 (got {n_trials})"
        raise ValueError(msg)

    base_settings = Settings.from_yaml(base_config_path)
    # 入力ディレクトリを絶対パス化（CI の cwd ずれに強くする）
    input_abs = _resolve_input_dir(base_config_path, base_settings)

    # 100 世帯（既定）以外を要求された場合のみスケール処理を行う。
    # _scale_sample_case は data/sample_case/ を整数倍スケールするため、
    # 100 の倍数のみ受け付ける。100 のときは何もせず素通しにすれば、
    # CI 既定の挙動（既存 expected/*.csv の値）と一致する。
    if n_households is None or n_households == 100:
        df = _run_with_input(
            base_settings=base_settings,
            input_dir=input_abs,
            output_root=output_root,
            seed=seed,
            strategy_name=strategy_name,
            n_trials=n_trials,
        )
    else:
        # 遅延 import で循環参照を避ける（runner.py も improve_runner.py も
        # paper_results._shared 配下に同居しているため、トップレベル import は
        # 順序依存になる）。
        from paper_results._shared.runner import scale_sample_case

        with TemporaryDirectory() as tmp:
            scaled = Path(tmp) / "scaled_input"
            scale_sample_case(n_households, scaled)
            df = _run_with_input(
                base_settings=base_settings,
                input_dir=scaled,
                output_root=output_root,
                seed=seed,
                strategy_name=strategy_name,
                n_trials=n_trials,
            )
    return df


def _run_with_input(
    *,
    base_settings: Settings,
    input_dir: Path,
    output_root: Path,
    seed: int,
    strategy_name: str,
    n_trials: int,
) -> pd.DataFrame:
    """input_dir を差し替えて improve loop を 1 回回し DataFrame を組み立てる."""
    settings = base_settings.model_copy(
        update={
            "seed": int(seed),
            "input_dir": input_dir.resolve(),
            "output_dir": output_root.resolve(),
        },
    )

    strategy_typed = cast(StrategyName, strategy_name)
    result = run_improve_loop(
        settings,
        strategy_name=strategy_typed,
        n_trials=n_trials,
        seed=int(seed),
        output_root=output_root.resolve(),
    )

    rows = [_trial_to_row(seed=seed, strategy_name=strategy_name, tr=tr) for tr in result.history]
    df = pd.DataFrame(rows)
    df = _attach_composite(df)
    return df


__all__ = ["run_improve_for_paper_results"]
