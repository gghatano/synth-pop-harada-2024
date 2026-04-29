"""Evaluator plugin discovery via entry_points (Issue #79).

第三者が別パッケージの ``pyproject.toml`` で

.. code-block:: toml

    [project.entry-points."synthpop_jp.evaluators"]
    my_evaluator = "my_pkg.evaluators:MyEvaluator"

のように登録した Evaluator factory を、``synthpop-jp evaluate`` が自動検出して
実行できるようにする。

設計
----
- entry_points group: ``synthpop_jp.evaluators``
- 各 entry point は **無引数 callable**（クラスでも関数でも可）。呼ぶと
  :class:`~synthpop_jp.domain.protocols.Evaluator` Protocol を満たす instance を返す。
- Protocol 違反のものは ``UserWarning`` を出してスキップ。
- 複雑な context（real_persons など）を必要とする evaluator は本機構の対象外
  （今後の拡張で対応）。

テスト戦略
----------
``importlib.metadata.entry_points`` を直接モックするのは難しいため、
本モジュール内に薄いラッパー ``_discover_entry_points`` を置き、テストでは
これを ``monkeypatch`` で差し替える。
"""

from __future__ import annotations

import warnings
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from synthpop_jp.domain.protocols import Evaluator

if TYPE_CHECKING:
    from importlib.metadata import EntryPoint

_GROUP: str = "synthpop_jp.evaluators"


def _discover_entry_points(group: str) -> Iterable[EntryPoint]:
    """``importlib.metadata.entry_points`` の薄いラッパー (テスト差し替え用)."""
    from importlib.metadata import entry_points

    return entry_points(group=group)


def load_evaluator_plugins() -> list[Evaluator]:
    """``synthpop_jp.evaluators`` group の entry_points から Evaluator を読み込む.

    各 entry point が ``Evaluator`` Protocol を満たさない場合は ``UserWarning``
    を出してスキップする。

    Returns
    -------
    list[Evaluator]
        Protocol を満たす evaluator instance のリスト。entry_points 未登録時は
        空リスト。
    """
    plugins: list[Evaluator] = []
    for ep in _discover_entry_points(_GROUP):
        try:
            factory: Any = ep.load()
            instance = factory()
        except (ImportError, AttributeError, TypeError) as e:
            warnings.warn(
                f"Evaluator plugin '{ep.name}' の読み込みに失敗: {e}",
                stacklevel=2,
            )
            continue
        if not isinstance(instance, Evaluator):
            warnings.warn(
                f"Evaluator plugin '{ep.name}' が Evaluator Protocol を満たしません",
                stacklevel=2,
            )
            continue
        plugins.append(instance)
    return plugins
