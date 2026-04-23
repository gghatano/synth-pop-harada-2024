"""Structural contracts for synthpop-jp extension points.

The Protocols defined here are the boundary between the internal SA
implementation (``optimize/``) and pluggable extensions
(transitions, cooling schedules, evaluators, privacy metrics). They are
``runtime_checkable`` so that lightweight ``isinstance`` checks can be used
at registration time; strict type-level verification happens through
pyright.

See ``docs/reviews/review-python.md`` 指摘5 for the rationale.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, Protocol, runtime_checkable

PrivacyLayer = Literal["proxy", "attribute_inference", "mia"]
"""Evaluation layers for :class:`PrivacyMetric`.

See ``docs/spec/metrics.md`` and ADR-0003 for why this boundary is enforced at
the type level.
"""

if TYPE_CHECKING:
    import numpy as np
    from numpy.random import Generator

    from synthpop_jp.optimize.state import PopulationArrays, Proposal


@runtime_checkable
class Transition(Protocol):
    """An SA transition proposing and committing a local state change.

    Attributes
    ----------
    name : str
        Stable identifier used for logging and registry lookup.
    """

    name: str

    def propose(self, state: PopulationArrays, rng: Generator) -> Proposal:
        """Propose a change to ``state`` using ``rng``."""
        ...

    def apply(self, state: PopulationArrays, proposal: Proposal) -> None:
        """Apply ``proposal`` to ``state`` in place."""
        ...

    def revert(self, state: PopulationArrays, proposal: Proposal) -> None:
        """Revert a previously applied ``proposal`` on ``state``."""
        ...


@runtime_checkable
class CoolingSchedule(Protocol):
    """A temperature schedule for Simulated Annealing."""

    def temperature(self, iter: int) -> float:
        """Return the temperature at iteration ``iter``."""
        ...


@runtime_checkable
class Evaluator(Protocol):
    """An evaluator reducing a population to a metric dictionary.

    Attributes
    ----------
    name : str
        Stable identifier used in ``metrics.json``.
    """

    name: str

    def evaluate(self, pop: PopulationArrays) -> dict[str, float]:
        """Return a flat ``{metric_name: value}`` mapping for ``pop``."""
        ...


@runtime_checkable
class Distribution(Protocol):
    """Abstraction over a (possibly noisy) target distribution.

    The Phase 0 scaffold only ships deterministic targets. The Protocol is
    declared now so that future DP-aware targets can be dropped in without
    breaking callers (see ``docs/reviews/review-privacy.md`` S7).
    """

    def mean(self) -> np.ndarray[Any, Any]:
        """Return the point estimate of the target distribution."""
        ...

    def sample(self, rng: Generator) -> np.ndarray[Any, Any]:
        """Draw a single sample from the target distribution using ``rng``."""
        ...


@runtime_checkable
class PrivacyMetric(Protocol):
    """A privacy metric at a specific evaluation layer.

    Attributes
    ----------
    name : str
        Stable identifier used in ``metrics.json``.
    layer : PrivacyLayer
        One of ``"proxy"``, ``"attribute_inference"``, or ``"mia"``; see
        ``docs/reviews/review-privacy.md`` for the layer definitions.
    """

    name: str
    layer: PrivacyLayer

    def evaluate(
        self,
        synthetic: PopulationArrays,
        holdout: PopulationArrays,
    ) -> dict[str, float]:
        """Return a flat metric dictionary comparing ``synthetic`` with ``holdout``."""
        ...
