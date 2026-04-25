"""ベンチマークテストパッケージ (Issue #33).

このパッケージは synthpop-jp の性能ゲート検証テストを収録する。

成功条件（action-plan §3.4 Phase 2 Exit）:
- objective.propose_change 1 回 < 100 μs
- transition.propose 1 回 < 10 μs
- SA 1000 世帯 × 20 万反復 < 30 秒

通常の pytest 実行では --benchmark-skip が効いてスキップされる。
``uv run pytest -m benchmark`` で全 benchmark を実行できる。
"""
