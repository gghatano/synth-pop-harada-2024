"""Verify ``runtime_checkable`` behaviour of the domain protocols."""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.random import Generator

from synthpop_jp.domain.protocols import (
    CoolingSchedule,
    Evaluator,
    Transition,
)
from synthpop_jp.optimize.state import PopulationArrays, Proposal


class FakeTransition:
    """Minimal transition that honours the Transition Protocol."""

    name: str = "fake"

    def propose(self, state: PopulationArrays, rng: Generator) -> Proposal:
        del state, rng
        empty = np.empty(0, dtype=np.int32)
        return Proposal(transition=self.name, indices=empty, before=empty, after=empty)

    def apply(self, state: PopulationArrays, proposal: Proposal) -> None:
        del state, proposal

    def revert(self, state: PopulationArrays, proposal: Proposal) -> None:
        del state, proposal


class FakeCoolingSchedule:
    def temperature(self, iter: int) -> float:
        return 1.0 / (iter + 1)


class FakeEvaluator:
    name: str = "fake-eval"

    def evaluate(self, pop: PopulationArrays) -> dict[str, float]:
        del pop
        return {"loss": 0.0}


def test_fake_transition_is_transition() -> None:
    assert isinstance(FakeTransition(), Transition)


def test_fake_cooling_is_cooling_schedule() -> None:
    assert isinstance(FakeCoolingSchedule(), CoolingSchedule)


def test_fake_evaluator_is_evaluator() -> None:
    assert isinstance(FakeEvaluator(), Evaluator)


def test_non_transition_rejected() -> None:
    class NotATransition:
        name: str = "x"

    obj: Any = NotATransition()
    assert not isinstance(obj, Transition)
