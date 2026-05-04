"""Tests for paper_results/experiment-04 ``--full`` mode.

experiment-04 をフル設定（n=10 / n_trials=20 / 1000 世帯）で `expected-full/`
に書き出せる骨格を確認する。実 SA は重いため、ここでは:

1. ``FULL_SEEDS`` / ``FULL_N_TRIALS`` / ``FULL_HOUSEHOLDS`` 定数
2. ``--full`` フラグ
3. ``_output_dir(full=True)`` が ``expected-full/`` を返す
4. CI 定数（5 seeds / 5 trials / 100 世帯）が維持される

を確認する。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
EXP04_DIR = REPO_ROOT / "paper_results" / "experiment-04-multi-trial-variance"
RUN_PY = EXP04_DIR / "run.py"


def _load_run_module() -> object:
    spec = importlib.util.spec_from_file_location("paper_results_exp04_run_full", RUN_PY)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestExperiment04FullConstants:
    """フル設定の定数."""

    def test_full_seeds_is_five_seeds(self) -> None:
        # scale-up smoke：n=10 → n=5（exp03 と同じ理由で計算量を圧縮）
        m = _load_run_module()
        assert hasattr(m, "FULL_SEEDS")
        assert tuple(m.FULL_SEEDS) == (1, 2, 3, 4, 5)  # type: ignore[attr-defined]

    def test_full_n_trials_is_ten(self) -> None:
        m = _load_run_module()
        assert hasattr(m, "FULL_N_TRIALS")
        assert m.FULL_N_TRIALS == 10  # type: ignore[attr-defined]

    def test_full_households_is_five_hundred(self) -> None:
        m = _load_run_module()
        assert hasattr(m, "FULL_HOUSEHOLDS")
        assert m.FULL_HOUSEHOLDS == 500  # type: ignore[attr-defined]

    def test_ci_constants_unchanged(self) -> None:
        m = _load_run_module()
        assert tuple(m.CI_SEEDS) == (1, 2, 3, 4, 5)  # type: ignore[attr-defined]
        assert m.CI_N_TRIALS == 5  # type: ignore[attr-defined]
        assert m.CI_HOUSEHOLDS == 100  # type: ignore[attr-defined]


class TestExperiment04FullCli:
    """CLI レベルでの --full フラグ."""

    def test_full_flag_accepted_by_parser(self) -> None:
        m = _load_run_module()
        with pytest.raises(SystemExit) as exc:
            m.main(["--full", "--help"])  # type: ignore[attr-defined]
        assert exc.value.code == 0

    def test_output_dir_full_returns_expected_full(self) -> None:
        m = _load_run_module()
        assert hasattr(m, "_output_dir")
        out_full = m._output_dir(full=True)  # type: ignore[attr-defined]
        out_ci = m._output_dir(full=False)  # type: ignore[attr-defined]
        assert out_full.name == "expected-full"
        assert out_ci.name == "expected"
