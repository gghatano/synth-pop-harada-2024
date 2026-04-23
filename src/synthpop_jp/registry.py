"""Plugin registry stubs for synthpop-jp.

External packages register extensions through the entry-point groups declared
in ``pyproject.toml`` (``synthpop_jp.evaluators``, ``synthpop_jp.transitions``,
``synthpop_jp.family_types``). The Phase 0 stubs below reserve the public API
surface; the actual discovery and invocation is implemented in Phase 3+
(see ``docs/reviews/review-oss.md`` 指摘5).

The in-process ``register_*`` functions below are meant to coexist with the
entry-points declared in ``pyproject.toml``. Phase 3 will unify them so that
both surfaces share a single lookup path; Phase 0 only reserves the API shape.
"""

from __future__ import annotations

from typing import Any


def register_family_type(name: str, template: Any) -> None:
    """Register a new ``family_type`` template.

    Parameters
    ----------
    name : str
        Unique identifier of the family type.
    template : Any
        Template describing roles, age distributions, etc. The concrete type
        is defined in Phase 1.
    """
    raise NotImplementedError("register_family_type is implemented in Phase 1/3.")


def register_transition(name: str, transition: Any) -> None:
    """Register a new SA transition.

    Parameters
    ----------
    name : str
        Unique identifier of the transition.
    transition : Any
        Object implementing the :class:`~synthpop_jp.domain.protocols.Transition`
        protocol.
    """
    raise NotImplementedError("register_transition is implemented in Phase 2/3.")


def register_evaluator(name: str, evaluator: Any) -> None:
    """Register a new evaluator.

    Parameters
    ----------
    name : str
        Unique identifier of the evaluator.
    evaluator : Any
        Object implementing the :class:`~synthpop_jp.domain.protocols.Evaluator`
        protocol.
    """
    raise NotImplementedError("register_evaluator is implemented in Phase 3.5.")
