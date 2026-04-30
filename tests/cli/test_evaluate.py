"""Tests for the ``evaluate`` CLI subcommand (Phase 3.5, Issue #59).

generate → evaluate を tmp_path 上で順番実行し、metrics.json に
``aggregate.l1.*`` キーが追記されることを検証する。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from synthpop_jp.cli import app

runner = CliRunner()

SAMPLE_CASE_DIR = Path(__file__).parent.parent.parent / "data" / "sample_case"


def _make_config_yaml(tmp_path: Path) -> Path:
    """generate + evaluate 共通の小さい config を作る."""
    config_data: dict[str, object] = {
        "seed": 42,
        "input_dir": str(SAMPLE_CASE_DIR),
        "output_dir": str(tmp_path / "out"),
        "annealing": {
            "T0": 100.0,
            "alpha": 0.99,
            "max_iters": 200,
            "evals_per_agent": 0,
            "target_threshold": 0.0,
            "patience": 0,
        },
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config_data))
    return config_path


@pytest.mark.slow
class TestEvaluateIntegration:
    """end-to-end: generate → evaluate を順番に実行する."""

    def test_evaluate_appends_aggregate_keys(self, tmp_path: Path) -> None:
        """evaluate 後の metrics.json に aggregate.l1.* キーが含まれる."""
        config_path = _make_config_yaml(tmp_path)
        gen_result = runner.invoke(app, ["generate", "--config", str(config_path)])
        assert gen_result.exit_code == 0, gen_result.output

        eval_result = runner.invoke(app, ["evaluate", "--config", str(config_path)])
        assert eval_result.exit_code == 0, eval_result.output

        metrics_path = tmp_path / "out" / "metrics.json"
        assert metrics_path.exists()
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))

        # aggregate.l1.* が 5 stat + total = 6 キー含まれる
        assert "aggregate.l1.father_child_age_diff" in metrics
        assert "aggregate.l1.mother_child_age_diff" in metrics
        assert "aggregate.l1.couple_age_diff" in metrics
        assert "aggregate.l1.pyramid_male" in metrics
        assert "aggregate.l1.pyramid_female" in metrics
        assert "aggregate.l1.total" in metrics

        # 既存 generate キーが保持される
        assert "total_households" in metrics
        assert "best_score" in metrics

    def test_evaluate_aggregate_total_matches_best_score(self, tmp_path: Path) -> None:
        """evaluate の aggregate.l1.total は generate の best_score と一致."""
        config_path = _make_config_yaml(tmp_path)
        runner.invoke(app, ["generate", "--config", str(config_path)])
        runner.invoke(app, ["evaluate", "--config", str(config_path)])

        metrics_path = tmp_path / "out" / "metrics.json"
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        # best_score は generate が書いた値、aggregate.l1.total は evaluate が計算
        # 同じ最終人口に対する L1 なので一致する
        assert abs(metrics["aggregate.l1.total"] - metrics["best_score"]) < 1e-3

    def test_evaluate_appends_rare_cell_keys(self, tmp_path: Path) -> None:
        """evaluate 後の metrics.json に rare_cell.* キーが含まれる（Issue #61）."""
        config_path = _make_config_yaml(tmp_path)
        gen_result = runner.invoke(app, ["generate", "--config", str(config_path)])
        assert gen_result.exit_code == 0, gen_result.output
        eval_result = runner.invoke(app, ["evaluate", "--config", str(config_path)])
        assert eval_result.exit_code == 0, eval_result.output

        metrics = json.loads((tmp_path / "out" / "metrics.json").read_text(encoding="utf-8"))
        assert "rare_cell.total_cells" in metrics
        assert "rare_cell.fraction_below_5" in metrics
        assert "rare_cell.fraction_unique" in metrics
        # per_family_type 分解（少なくとも 1 つの family_type について存在）
        assert any(k.startswith("rare_cell.per_family_type.") for k in metrics)

    def test_evaluate_fails_without_synthetic_csv(self, tmp_path: Path) -> None:
        """generate を先に実行していない場合は exit code 1."""
        config_path = _make_config_yaml(tmp_path)
        # generate せずに evaluate
        eval_result = runner.invoke(app, ["evaluate", "--config", str(config_path)])
        assert eval_result.exit_code == 1
        assert "synthetic_persons.csv" in eval_result.output

    def test_evaluate_skips_cap_without_real_persons_csv(self, tmp_path: Path) -> None:
        """``--real-persons-csv`` 未指定時は ``cap.*`` が含まれず、警告が出る（Issue #65）."""
        config_path = _make_config_yaml(tmp_path)
        runner.invoke(app, ["generate", "--config", str(config_path)])
        eval_result = runner.invoke(app, ["evaluate", "--config", str(config_path)])
        assert eval_result.exit_code == 0
        metrics = json.loads((tmp_path / "out" / "metrics.json").read_text(encoding="utf-8"))
        assert not any(k.startswith("cap.") for k in metrics)
        assert "CAP" in eval_result.output or "cap" in eval_result.output.lower()

    def test_evaluate_appends_cap_keys_with_real_persons_csv(self, tmp_path: Path) -> None:
        """``--real-persons-csv`` を指定すると ``cap.*`` キーが追記される（Issue #65）."""
        config_path = _make_config_yaml(tmp_path)
        gen_result = runner.invoke(app, ["generate", "--config", str(config_path)])
        assert gen_result.exit_code == 0, gen_result.output
        # synthetic を holdout 代わりに使う（self-eval だが CLI 動作確認には十分）
        synthetic_csv = tmp_path / "out" / "synthetic_persons.csv"
        eval_result = runner.invoke(
            app,
            [
                "evaluate",
                "--config",
                str(config_path),
                "--real-persons-csv",
                str(synthetic_csv),
            ],
        )
        assert eval_result.exit_code == 0, eval_result.output
        metrics = json.loads((tmp_path / "out" / "metrics.json").read_text(encoding="utf-8"))
        assert "cap.generalized" in metrics
        assert "cap.targeted" in metrics
        assert "cap.coverage" in metrics
        # holdout = synthetic なので perfect coverage
        assert abs(metrics["cap.coverage"] - 1.0) < 1e-9

    def test_evaluate_appends_broad_and_narrow_utility_keys(self, tmp_path: Path) -> None:
        """real-persons-csv 指定時に utility キーが追記される (#96, #97)."""
        config_path = _make_config_yaml(tmp_path)
        runner.invoke(app, ["generate", "--config", str(config_path)])
        synthetic_csv = tmp_path / "out" / "synthetic_persons.csv"
        eval_result = runner.invoke(
            app,
            [
                "evaluate",
                "--config",
                str(config_path),
                "--real-persons-csv",
                str(synthetic_csv),
            ],
        )
        assert eval_result.exit_code == 0, eval_result.output
        metrics = json.loads((tmp_path / "out" / "metrics.json").read_text(encoding="utf-8"))
        # broad utility
        for attr in ("age", "sex", "role", "family_type"):
            assert f"broad_utility.tv.{attr}" in metrics
            assert f"broad_utility.l1.{attr}" in metrics
        assert "broad_utility.pair_tv.age__sex" in metrics
        assert "broad_utility.correlation_frobenius_diff" in metrics
        assert metrics["broad_utility.tv.age"] == 0.0
        assert metrics["broad_utility.correlation_frobenius_diff"] == 0.0
        # narrow utility
        for task in ("task_a", "task_b", "task_c"):
            if task == "task_b":
                assert f"narrow_utility.{task}.tstr_rmse" in metrics
                assert f"narrow_utility.{task}.trts_rmse" in metrics
            else:
                assert f"narrow_utility.{task}.tstr_macro_f1" in metrics
                assert f"narrow_utility.{task}.trts_macro_f1" in metrics

    def test_evaluate_appends_dcr_nndr_ard_keys_with_real_persons_csv(
        self, tmp_path: Path
    ) -> None:
        """real-persons-csv 指定で dcr / nndr / ard キーが追記される (Issue #99)."""
        config_path = _make_config_yaml(tmp_path)
        runner.invoke(app, ["generate", "--config", str(config_path)])
        synthetic_csv = tmp_path / "out" / "synthetic_persons.csv"
        eval_result = runner.invoke(
            app,
            [
                "evaluate",
                "--config",
                str(config_path),
                "--real-persons-csv",
                str(synthetic_csv),
            ],
        )
        assert eval_result.exit_code == 0, eval_result.output
        metrics = json.loads((tmp_path / "out" / "metrics.json").read_text(encoding="utf-8"))
        assert "dcr.p05" in metrics
        assert "dcr.mean" in metrics
        assert "nndr.mean" in metrics
        assert "ard.mean" in metrics
        assert metrics["dcr.p05"] == 0.0
        assert metrics["dcr.mean"] == 0.0

    def test_evaluate_skips_utility_without_real_persons_csv(self, tmp_path: Path) -> None:
        """real-persons-csv 未指定で utility キーが含まれない (#96, #97)."""
        config_path = _make_config_yaml(tmp_path)
        runner.invoke(app, ["generate", "--config", str(config_path)])
        eval_result = runner.invoke(app, ["evaluate", "--config", str(config_path)])
        assert eval_result.exit_code == 0
        metrics = json.loads((tmp_path / "out" / "metrics.json").read_text(encoding="utf-8"))
        assert not any(k.startswith("broad_utility.") for k in metrics)
        assert not any(k.startswith("narrow_utility.") for k in metrics)

    def test_evaluate_fails_with_missing_real_persons_csv(self, tmp_path: Path) -> None:
        """``--real-persons-csv`` のパスが無ければ exit code 1（Issue #65）."""
        config_path = _make_config_yaml(tmp_path)
        runner.invoke(app, ["generate", "--config", str(config_path)])
        eval_result = runner.invoke(
            app,
            [
                "evaluate",
                "--config",
                str(config_path),
                "--real-persons-csv",
                str(tmp_path / "does_not_exist.csv"),
            ],
        )
        assert eval_result.exit_code == 1
        assert "real-persons-csv" in eval_result.output

    def test_evaluate_writes_report_md_by_default(self, tmp_path: Path) -> None:
        """evaluate 完了で output_dir/report.md が生成される (Issue #78)."""
        config_path = _make_config_yaml(tmp_path)
        runner.invoke(app, ["generate", "--config", str(config_path)])
        result = runner.invoke(app, ["evaluate", "--config", str(config_path)])
        assert result.exit_code == 0, result.output
        report_path = tmp_path / "out" / "report.md"
        assert report_path.exists()
        report = report_path.read_text(encoding="utf-8")
        assert report.startswith("# ")
        assert "aggregate" in report.lower() or "L1" in report

    def test_evaluate_no_report_flag_skips_report_md(self, tmp_path: Path) -> None:
        """--no-report 指定で report.md が生成されない (Issue #78)."""
        config_path = _make_config_yaml(tmp_path)
        runner.invoke(app, ["generate", "--config", str(config_path)])
        result = runner.invoke(app, ["evaluate", "--config", str(config_path), "--no-report"])
        assert result.exit_code == 0, result.output
        report_path = tmp_path / "out" / "report.md"
        assert not report_path.exists()
        assert (tmp_path / "out" / "metrics.json").exists()

    def test_evaluate_strict_extended_omits_pyramid_male_female(self, tmp_path: Path) -> None:
        """strict_extended config (use_family_type_pyramid + exclude_male_female_pyramid)
        で metrics.json に pyramid_male/pyramid_female キーが含まれない (Issue #76)."""
        config_data: dict[str, object] = {
            "seed": 42,
            "input_dir": str(SAMPLE_CASE_DIR),
            "output_dir": str(tmp_path / "out"),
            "annealing": {
                "T0": 100.0,
                "alpha": 0.99,
                "max_iters": 200,
                "evals_per_agent": 0,
                "target_threshold": 0.0,
                "patience": 0,
            },
            "objective": {
                "use_family_type_pyramid": True,
                "exclude_male_female_pyramid": True,
            },
        }
        config_path = tmp_path / "config_strict.yaml"
        config_path.write_text(yaml.dump(config_data))
        gen_result = runner.invoke(app, ["generate", "--config", str(config_path)])
        assert gen_result.exit_code == 0, gen_result.output
        eval_result = runner.invoke(app, ["evaluate", "--config", str(config_path)])
        assert eval_result.exit_code == 0, eval_result.output
        metrics = json.loads((tmp_path / "out" / "metrics.json").read_text(encoding="utf-8"))
        assert "aggregate.l1.pyramid_male" not in metrics
        assert "aggregate.l1.pyramid_female" not in metrics
        assert "aggregate.l1.father_child_age_diff" in metrics
        assert any(k.startswith("aggregate.l1.pyramid_per_family_type.") for k in metrics)

    def test_evaluate_calls_entry_point_plugins(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """entry_points 登録された plugin の metric が metrics.json に追記される (Issue #79)."""

        from synthpop_jp.optimize.state import PopulationArrays

        class _DummyPlugin:
            name: str = "plugin_dummy"

            def evaluate(self, pop: PopulationArrays) -> dict[str, float]:
                return {"plugin_dummy.score": float(pop.n_persons)}

        monkeypatch.setattr(
            "synthpop_jp.evaluate.plugin.load_evaluator_plugins",
            lambda: [_DummyPlugin()],
        )

        config_path = _make_config_yaml(tmp_path)
        gen_result = runner.invoke(app, ["generate", "--config", str(config_path)])
        assert gen_result.exit_code == 0, gen_result.output
        eval_result = runner.invoke(app, ["evaluate", "--config", str(config_path)])
        assert eval_result.exit_code == 0, eval_result.output

        metrics = json.loads((tmp_path / "out" / "metrics.json").read_text(encoding="utf-8"))
        assert "plugin_dummy.score" in metrics
        assert "aggregate.l1.total" in metrics
        assert "rare_cell.total_cells" in metrics

    def test_evaluate_appends_pyramid_per_family_type_keys(self, tmp_path: Path) -> None:
        """use_family_type_pyramid=True の config で evaluate が
        ``aggregate.l1.pyramid_per_family_type.<ft>.<sex>`` キーを出力する (Issue #71)."""
        config_data: dict[str, object] = {
            "seed": 42,
            "input_dir": str(SAMPLE_CASE_DIR),
            "output_dir": str(tmp_path / "out"),
            "annealing": {
                "T0": 100.0,
                "alpha": 0.99,
                "max_iters": 200,
                "evals_per_agent": 0,
                "target_threshold": 0.0,
                "patience": 0,
            },
            "objective": {"use_family_type_pyramid": True},
        }
        config_path = tmp_path / "config_extended.yaml"
        config_path.write_text(yaml.dump(config_data))
        gen_result = runner.invoke(app, ["generate", "--config", str(config_path)])
        assert gen_result.exit_code == 0, gen_result.output
        eval_result = runner.invoke(app, ["evaluate", "--config", str(config_path)])
        assert eval_result.exit_code == 0, eval_result.output

        metrics = json.loads((tmp_path / "out" / "metrics.json").read_text(encoding="utf-8"))
        assert any(k.startswith("aggregate.l1.pyramid_per_family_type.") for k in metrics), (
            f"pyramid_per_family_type キーが含まれない: keys={list(metrics)[:20]}"
        )
