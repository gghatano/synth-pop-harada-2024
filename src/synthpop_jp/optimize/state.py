"""SA state containers.

The :class:`PopulationArrays` dataclass is the internal parallel-array
representation used by the Simulated Annealing inner loop (see
``docs/reviews/review-python.md`` 指摘1 and ADR-0001). The boundary with
the pydantic domain models lives in :mod:`synthpop_jp.domain`.

The fields are placeholders in Phase 0; they will be filled by the
converters implemented in Phase 1.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class PopulationArrays:
    """Parallel NumPy arrays representing the population during SA.

    Attributes
    ----------
    age : np.ndarray
        ``int16`` array of shape ``(n_persons,)`` holding individual ages.
    sex : np.ndarray
        ``int8`` array, ``0`` for male and ``1`` for female.
    role : np.ndarray
        ``int8`` enum array encoding the role within a household.
    household_id : np.ndarray
        ``int32`` array mapping each person to their household.
    family_type : np.ndarray
        ``int8`` enum array holding the family type for each person
        (broadcast from their household).
    """

    age: np.ndarray[Any, Any]
    sex: np.ndarray[Any, Any]
    role: np.ndarray[Any, Any]
    household_id: np.ndarray[Any, Any]
    family_type: np.ndarray[Any, Any]


@dataclass
class Proposal:
    """A proposed SA transition.

    Attributes
    ----------
    transition : str
        Name of the transition that produced this proposal.
    indices : np.ndarray
        Indices (into :class:`PopulationArrays`) affected by the proposal.
    before : np.ndarray
        Pre-change values (for reversal).
    after : np.ndarray
        Post-change values.
    """

    transition: str
    indices: np.ndarray[Any, Any]
    before: np.ndarray[Any, Any]
    after: np.ndarray[Any, Any]
