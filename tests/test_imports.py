"""Smoke test: the synthpop_jp package imports without side effects."""

from __future__ import annotations


def test_import_package() -> None:
    import synthpop_jp

    assert synthpop_jp.__version__ == "0.0.0"


def test_import_subpackages() -> None:
    import synthpop_jp.cli
    import synthpop_jp.config
    import synthpop_jp.domain.protocols
    import synthpop_jp.optimize.state
    import synthpop_jp.registry

    assert synthpop_jp.cli.app is not None
    assert synthpop_jp.domain.protocols.Transition is not None
    assert synthpop_jp.optimize.state.PopulationArrays is not None
    assert synthpop_jp.config is not None
    assert synthpop_jp.registry is not None
