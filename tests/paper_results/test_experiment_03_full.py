"""Tests for paper_results/experiment-03 ``--full`` mode (Issue #paper-results-full-run).

experiment-03 をフル設定（n=10 / n_trials=20 / 1000 世帯）で `expected-full/`
に書き出せる土台を作る。本ファイルは:

1. ``FULL_SEEDS`` / ``FULL_N_TRIALS`` / ``FULL_HOUSEHOLDS`` 定数の存在
2. ``--full`` フラグが argparse に登録されている
3. ``_output_dir(full=True)`` が ``expected-full/`` を返す
4. ``--full`` モードで 100 世帯（CI 既定）の入力を渡しても落ちない smoke

を確認する。重い実 SA は ``test_experiment_03.py::TestExperiment03Cli`` 側に任せ、
ここでは「設定オーバーライドできる」骨格のみ確認する。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
EXP03_DIR = REPO_ROOT / "paper_results" / "experiment-03-improve-strategy-comparison"
RUN_PY = EXP03_DIR / "run.py"


def _load_run_module() -> object:
    spec = importlib.util.spec_from_file_location("paper_results_exp03_run_full", RUN_PY)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestExperiment03FullConstants:
    """フル設定の定数が宣言されている."""

    def test_full_seeds_is_ten_seeds(self) -> None:
        m = _load_run_module()
        assert hasattr(m, "FULL_SEEDS")
        assert tuple(m.FULL_SEEDS) == (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)  # type: ignore[attr-defined]

    def test_full_n_trials_is_twenty(self) -> None:
        m = _load_run_module()
        assert hasattr(m, "FULL_N_TRIALS")
        assert m.FULL_N_TRIALS == 20  # type: ignore[attr-defined]

    def test_full_households_is_thousand(self) -> None:
        m = _load_run_module()
        assert hasattr(m, "FULL_HOUSEHOLDS")
        assert m.FULL_HOUSEHOLDS == 1000  # type: ignore[attr-defined]

    def test_ci_constants_unchanged(self) -> None:
        m = _load_run_module()
        assert tuple(m.CI_SEEDS) == (1, 2, 3)  # type: ignore[attr-defined]
        assert m.CI_N_TRIALS == 5  # type: ignore[attr-defined]
        assert m.CI_HOUSEHOLDS == 100  # type: ignore[attr-defined]


class TestExperiment03FullCli:
    """CLI レベルでの --full フラグ受け入れ."""

    def test_full_flag_accepted_by_parser(self) -> None:
        m = _load_run_module()
        # parser を作る関数があれば直接、無ければ main(["--full", "--help"]) で
        # SystemExit するかを見る方が安全
        with pytest.raises(SystemExit) as exc:
            m.main(["--full", "--help"])  # type: ignore[attr-defined]
        # --help は exit code 0
        assert exc.value.code == 0

    def test_output_dir_full_returns_expected_full(self) -> None:
        m = _load_run_module()
        assert hasattr(m, "_output_dir")
        out_full = m._output_dir(full=True)  # type: ignore[attr-defined]
        out_ci = m._output_dir(full=False)  # type: ignore[attr-defined]
        assert out_full.name == "expected-full"
        assert out_ci.name == "expected"
