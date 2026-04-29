"""Tests for evaluator plugin discovery via entry_points (Issue #79)."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pytest

from synthpop_jp.domain.protocols import Evaluator
from synthpop_jp.evaluate.plugin import load_evaluator_plugins
from synthpop_jp.optimize.state import PopulationArrays


class _DummyEvaluator:
    """テスト用の最小 Evaluator."""

    name: str = "dummy"

    def evaluate(self, pop: PopulationArrays) -> dict[str, float]:
        return {"dummy.score": float(pop.n_persons)}


class _NotAnEvaluator:
    """Evaluator Protocol を満たさないもの (name 属性なし、evaluate メソッドなし)."""

    foo: str = "bar"


class _FakeEntryPoint:
    """importlib.metadata.EntryPoint の最小モック."""

    def __init__(self, name: str, factory: Any) -> None:
        self.name = name
        self._factory = factory

    def load(self) -> Any:
        return self._factory


class TestLoadEvaluatorPlugins:
    """load_evaluator_plugins の動作."""

    def test_returns_evaluator_from_entry_point(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """entry_points で登録された factory から Evaluator を取得する."""
        fake_eps: list[_FakeEntryPoint] = [_FakeEntryPoint("dummy", _DummyEvaluator)]

        def fake_discover(group: str) -> Iterable[_FakeEntryPoint]:
            del group
            return fake_eps

        monkeypatch.setattr("synthpop_jp.evaluate.plugin._discover_entry_points", fake_discover)

        plugins = load_evaluator_plugins()

        assert len(plugins) == 1
        assert isinstance(plugins[0], Evaluator)
        assert plugins[0].name == "dummy"

    def test_skips_non_evaluator_with_warning(
        self, monkeypatch: pytest.MonkeyPatch, recwarn: pytest.WarningsRecorder
    ) -> None:
        """Evaluator Protocol を満たさないものはスキップして warning を出す."""
        fake_eps: list[_FakeEntryPoint] = [_FakeEntryPoint("bad", _NotAnEvaluator)]

        def fake_discover(group: str) -> Iterable[_FakeEntryPoint]:
            del group
            return fake_eps

        monkeypatch.setattr("synthpop_jp.evaluate.plugin._discover_entry_points", fake_discover)

        plugins = load_evaluator_plugins()

        assert plugins == []
        assert any("bad" in str(w.message) for w in recwarn.list)

    def test_returns_empty_list_when_no_entry_points(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """entry_points が無いときは空リスト (既存挙動と等価)."""

        def fake_discover(group: str) -> Iterable[_FakeEntryPoint]:
            del group
            return []

        monkeypatch.setattr("synthpop_jp.evaluate.plugin._discover_entry_points", fake_discover)

        assert load_evaluator_plugins() == []
