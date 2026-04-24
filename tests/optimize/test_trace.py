"""Tests for TraceEvent, TraceWriter, read_trace — Issue #31.

TDD サイクル:
  Cycle 1: TraceEvent pydantic モデル（schema 通り）
  Cycle 2: TraceWriter.write(event) が 1 行 JSON を append
  Cycle 3: read_trace(path) が DataFrame に変換
  Cycle 4: AnnealingConfig に log_every_n_iters / trace_enabled 追加
  Cycle 5: SARunner.run に trace 統合（trace_enabled=True でファイル生成）
  Cycle 6: config.trace_enabled=False で trace ファイルが作られない
  Cycle 7: 更新頻度 log_every_n_iters の検証
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from synthpop_jp.config import AnnealingConfig
from synthpop_jp.domain.household import Household
from synthpop_jp.domain.person import Person
from synthpop_jp.domain.registry import FamilyTypeRegistry, RoleRegistry, SexRegistry
from synthpop_jp.optimize.state import PopulationArrays

# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------

ALL_ROLES = ["husband", "wife", "father", "mother", "child", "parent", "single"]
ALL_FAMILY_TYPES = [
    "couple",
    "couple_and_children",
    "single",
    "lone_parent_and_children",
    "couple_and_a_parent",
]


def make_registries() -> tuple[FamilyTypeRegistry, RoleRegistry, SexRegistry]:
    """テスト用 Registry を返す."""
    family_reg = FamilyTypeRegistry()
    for ft in ALL_FAMILY_TYPES:
        family_reg.register(ft)
    role_reg = RoleRegistry()
    for r in ALL_ROLES:
        role_reg.register(r)
    sex_reg = SexRegistry()
    return family_reg, role_reg, sex_reg


def make_small_arrays(n_persons: int = 10) -> PopulationArrays:
    """単純な配列を返す（テスト用）.

    全員を単身世帯（single）とする。
    """
    family_reg, role_reg, sex_reg = make_registries()
    households = [
        Household(
            household_id=i + 1,
            family_type="single",
            members=[
                Person(
                    household_id=i + 1,
                    role="single",  # type: ignore[arg-type]
                    sex="M",  # type: ignore[arg-type]
                    age=30 + i,
                )
            ],
        )
        for i in range(n_persons)
    ]
    return PopulationArrays.from_households(households, family_reg, role_reg, sex_reg)


# ---------------------------------------------------------------------------
# Cycle 1: TraceEvent pydantic モデル
# ---------------------------------------------------------------------------


class TestTraceEvent:
    """TraceEvent のスキーマ検証."""

    def test_trace_event_fields(self) -> None:
        """TraceEvent が必須フィールドをすべて持つ."""
        from synthpop_jp.optimize.trace import TraceEvent

        event = TraceEvent(
            iter=10,
            temperature=50.0,
            current_score=123.4,
            best_score=100.0,
            accepted=True,
            delta=-5.0,
            timestamp="2026-04-24T00:00:00Z",
        )
        assert event.iter == 10
        assert abs(event.temperature - 50.0) < 1e-9
        assert abs(event.current_score - 123.4) < 1e-9
        assert abs(event.best_score - 100.0) < 1e-9
        assert event.accepted is True
        assert abs(event.delta - (-5.0)) < 1e-9
        assert event.timestamp == "2026-04-24T00:00:00Z"

    def test_trace_event_json_serializable(self) -> None:
        """TraceEvent が JSON シリアライズ可能（1 行形式）."""
        from synthpop_jp.optimize.trace import TraceEvent

        event = TraceEvent(
            iter=1,
            temperature=99.0,
            current_score=200.0,
            best_score=200.0,
            accepted=False,
            delta=5.0,
            timestamp="2026-04-24T01:00:00Z",
        )
        serialized = event.model_dump_json()
        data = json.loads(serialized)
        assert data["iter"] == 1
        assert data["accepted"] is False

    def test_trace_event_requires_all_fields(self) -> None:
        """TraceEvent は必須フィールドが不足するとエラー."""
        from pydantic import ValidationError

        from synthpop_jp.optimize.trace import TraceEvent

        with pytest.raises(ValidationError):
            TraceEvent(  # type: ignore[call-arg]
                iter=1,
                temperature=10.0,
                # current_score 欠落
                best_score=10.0,
                accepted=True,
                delta=0.0,
                timestamp="2026-04-24T00:00:00Z",
            )


# ---------------------------------------------------------------------------
# Cycle 2: TraceWriter.write が 1 行 JSON を append
# ---------------------------------------------------------------------------


class TestTraceWriter:
    """TraceWriter の書き込みテスト."""

    def test_write_single_event(self, tmp_path: Path) -> None:
        """write() が 1 行 JSON を追記する."""
        from synthpop_jp.optimize.trace import TraceEvent, TraceWriter

        trace_path = tmp_path / "trace.jsonl"
        event = TraceEvent(
            iter=0,
            temperature=100.0,
            current_score=500.0,
            best_score=500.0,
            accepted=True,
            delta=-10.0,
            timestamp="2026-04-24T00:00:00Z",
        )

        with TraceWriter(trace_path) as writer:
            writer.write(event)

        lines = trace_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["iter"] == 0
        assert abs(data["temperature"] - 100.0) < 1e-9

    def test_write_multiple_events_appends(self, tmp_path: Path) -> None:
        """複数回 write() すると複数行になる."""
        from synthpop_jp.optimize.trace import TraceEvent, TraceWriter

        trace_path = tmp_path / "trace.jsonl"

        with TraceWriter(trace_path) as writer:
            for i in range(5):
                writer.write(
                    TraceEvent(
                        iter=i * 100,
                        temperature=100.0 - i,
                        current_score=500.0 - i,
                        best_score=500.0 - i,
                        accepted=True,
                        delta=-1.0,
                        timestamp="2026-04-24T00:00:00Z",
                    )
                )

        lines = trace_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 5
        # 最後の行の iter が 400 であること
        last = json.loads(lines[-1])
        assert last["iter"] == 400

    def test_writer_creates_parent_dir(self, tmp_path: Path) -> None:
        """親ディレクトリが存在しない場合でも自動作成する."""
        from synthpop_jp.optimize.trace import TraceEvent, TraceWriter

        trace_path = tmp_path / "nested" / "dir" / "trace.jsonl"

        with TraceWriter(trace_path) as writer:
            writer.write(
                TraceEvent(
                    iter=0,
                    temperature=100.0,
                    current_score=100.0,
                    best_score=100.0,
                    accepted=False,
                    delta=5.0,
                    timestamp="2026-04-24T00:00:00Z",
                )
            )

        assert trace_path.exists()


# ---------------------------------------------------------------------------
# Cycle 3: read_trace(path) -> pd.DataFrame
# ---------------------------------------------------------------------------


class TestReadTrace:
    """read_trace のテスト."""

    def test_read_trace_returns_dataframe(self, tmp_path: Path) -> None:
        """read_trace が DataFrame を返す."""
        import pandas as pd

        from synthpop_jp.optimize.trace import TraceEvent, TraceWriter, read_trace

        trace_path = tmp_path / "trace.jsonl"
        events = [
            TraceEvent(
                iter=i * 100,
                temperature=100.0 - i,
                current_score=500.0 - i * 2,
                best_score=500.0 - i * 2,
                accepted=True,
                delta=-2.0,
                timestamp="2026-04-24T00:00:00Z",
            )
            for i in range(3)
        ]
        with TraceWriter(trace_path) as writer:
            for e in events:
                writer.write(e)

        df = read_trace(trace_path)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3

    def test_read_trace_columns(self, tmp_path: Path) -> None:
        """DataFrame に iter / current_score カラムがある."""
        from synthpop_jp.optimize.trace import TraceEvent, TraceWriter, read_trace

        trace_path = tmp_path / "trace.jsonl"
        with TraceWriter(trace_path) as writer:
            writer.write(
                TraceEvent(
                    iter=42,
                    temperature=80.0,
                    current_score=300.0,
                    best_score=280.0,
                    accepted=False,
                    delta=20.0,
                    timestamp="2026-04-24T00:00:00Z",
                )
            )

        df = read_trace(trace_path)
        assert "iter" in df.columns
        assert "current_score" in df.columns
        assert "best_score" in df.columns
        assert "temperature" in df.columns
        assert "accepted" in df.columns

    def test_read_trace_values_match(self, tmp_path: Path) -> None:
        """DataFrame の値が書き込んだイベントと一致する."""
        from synthpop_jp.optimize.trace import TraceEvent, TraceWriter, read_trace

        trace_path = tmp_path / "trace.jsonl"
        with TraceWriter(trace_path) as writer:
            writer.write(
                TraceEvent(
                    iter=999,
                    temperature=55.5,
                    current_score=123.45,
                    best_score=100.0,
                    accepted=True,
                    delta=-23.45,
                    timestamp="2026-04-24T09:00:00Z",
                )
            )

        df = read_trace(trace_path)
        assert df["iter"].iloc[0] == 999
        assert abs(df["current_score"].iloc[0] - 123.45) < 1e-6
        assert abs(df["best_score"].iloc[0] - 100.0) < 1e-6


# ---------------------------------------------------------------------------
# Cycle 4: AnnealingConfig に log_every_n_iters / trace_enabled
# ---------------------------------------------------------------------------


class TestAnnealingConfigNewFields:
    """AnnealingConfig の新フィールドテスト."""

    def test_default_values(self) -> None:
        """log_every_n_iters=1000, trace_enabled=True がデフォルト."""
        config = AnnealingConfig()
        assert config.log_every_n_iters == 1000
        assert config.trace_enabled is True

    def test_custom_values(self) -> None:
        """カスタム値を設定できる."""
        config = AnnealingConfig(log_every_n_iters=500, trace_enabled=False)
        assert config.log_every_n_iters == 500
        assert config.trace_enabled is False

    def test_extra_field_forbidden(self) -> None:
        """extra="forbid" が維持されている."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            AnnealingConfig(unknown_field=True)  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# Cycle 5 & 6: SARunner.run に trace 統合 + trace_enabled=False
# ---------------------------------------------------------------------------


class TestSARunnerTraceIntegration:
    """SARunner.run の trace 統合テスト."""

    def _make_config(
        self,
        max_iters: int = 100,
        log_every_n_iters: int = 10,
        trace_enabled: bool = True,
    ) -> AnnealingConfig:
        return AnnealingConfig(
            T0=100.0,
            alpha=0.99,
            max_iters=max_iters,
            evals_per_agent=0,
            target_threshold=0.0,
            patience=0,
            log_every_n_iters=log_every_n_iters,
            trace_enabled=trace_enabled,
        )

    def _run_with_mock(
        self,
        config: AnnealingConfig,
        trace_path: Path | None = None,
        progress_enabled: bool = False,
    ) -> None:
        from synthpop_jp.optimize.annealing import SARunner
        from synthpop_jp.optimize.cooling import ExponentialCooling

        arrays = make_small_arrays(6)
        objective = MagicMock()
        objective.total_score = 100.0
        objective.propose_change.return_value = -0.01
        objective.apply_change.return_value = None

        transition = MagicMock()
        transition.propose.return_value = (0, 35)

        cooling = ExponentialCooling(T0=config.T0, alpha=config.alpha)
        rng = np.random.default_rng(42)
        runner = SARunner(rng=rng)

        runner.run(
            arrays=arrays,
            objective=objective,
            transition=transition,
            cooling=cooling,
            config=config,
            trace_path=trace_path,
            progress_enabled=progress_enabled,
        )

    def test_trace_file_created_when_enabled(self, tmp_path: Path) -> None:
        """trace_enabled=True + trace_path 指定でファイルが生成される."""
        trace_path = tmp_path / "trace.jsonl"
        config = self._make_config(max_iters=50, log_every_n_iters=10, trace_enabled=True)
        self._run_with_mock(config, trace_path=trace_path)

        assert trace_path.exists()
        lines = trace_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) > 0

    def test_trace_file_not_created_when_disabled(self, tmp_path: Path) -> None:
        """trace_enabled=False のとき trace ファイルが作られない."""
        trace_path = tmp_path / "trace.jsonl"
        config = self._make_config(max_iters=50, log_every_n_iters=10, trace_enabled=False)
        self._run_with_mock(config, trace_path=trace_path)

        assert not trace_path.exists()

    def test_trace_file_not_created_without_path(self, tmp_path: Path) -> None:  # noqa: ARG002
        """trace_path=None のとき trace ファイルが作られない."""
        config = self._make_config(max_iters=50, log_every_n_iters=10, trace_enabled=True)
        self._run_with_mock(config, trace_path=None)
        # 例外なく完了すれば OK

    def test_trace_line_count_matches_log_every_n_iters(self, tmp_path: Path) -> None:
        """trace の行数 = max_iters // log_every_n_iters."""
        max_iters = 100
        log_every = 10
        trace_path = tmp_path / "trace.jsonl"
        config = self._make_config(
            max_iters=max_iters,
            log_every_n_iters=log_every,
            trace_enabled=True,
        )
        self._run_with_mock(config, trace_path=trace_path)

        lines = trace_path.read_text(encoding="utf-8").splitlines()
        expected = max_iters // log_every
        assert len(lines) == expected, f"期待行数 {expected}、実際 {len(lines)}"

    def test_trace_event_schema_in_file(self, tmp_path: Path) -> None:
        """trace ファイルの各行が TraceEvent スキーマに準拠している."""
        trace_path = tmp_path / "trace.jsonl"
        config = self._make_config(max_iters=20, log_every_n_iters=10, trace_enabled=True)
        self._run_with_mock(config, trace_path=trace_path)

        lines = trace_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) > 0

        required_keys = {"iter", "temperature", "current_score", "best_score", "accepted", "delta", "timestamp"}
        for line in lines:
            data = json.loads(line)
            missing = required_keys - set(data.keys())
            assert not missing, f"trace 行にキーが不足: {missing}"


# ---------------------------------------------------------------------------
# Cycle 7: 更新頻度 log_every_n_iters
# ---------------------------------------------------------------------------


class TestLogEveryNIters:
    """log_every_n_iters の更新頻度テスト."""

    def test_trace_respects_log_every_n_iters(self, tmp_path: Path) -> None:
        """異なる log_every_n_iters で行数が変わる."""
        from synthpop_jp.optimize.annealing import SARunner
        from synthpop_jp.optimize.cooling import ExponentialCooling

        max_iters = 200

        for log_every in [10, 20, 50]:
            trace_path = tmp_path / f"trace_{log_every}.jsonl"
            config = AnnealingConfig(
                T0=100.0,
                alpha=0.99,
                max_iters=max_iters,
                evals_per_agent=0,
                target_threshold=0.0,
                patience=0,
                log_every_n_iters=log_every,
                trace_enabled=True,
            )

            arrays = make_small_arrays(6)
            objective = MagicMock()
            objective.total_score = 100.0
            objective.propose_change.return_value = -0.01
            objective.apply_change.return_value = None
            transition = MagicMock()
            transition.propose.return_value = (0, 35)

            cooling = ExponentialCooling(T0=100.0, alpha=0.99)
            rng = np.random.default_rng(42)
            runner = SARunner(rng=rng)

            runner.run(
                arrays=arrays,
                objective=objective,
                transition=transition,
                cooling=cooling,
                config=config,
                trace_path=trace_path,
                progress_enabled=False,
            )

            lines = trace_path.read_text(encoding="utf-8").splitlines()
            expected = max_iters // log_every
            assert len(lines) == expected, (
                f"log_every={log_every}: 期待行数 {expected}、実際 {len(lines)}"
            )
