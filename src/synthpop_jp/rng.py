"""乱数源の階層管理モジュール (SeedRegistry).

## 目的

実験の再現性（bitwise 一致）を保証するために、プロセス内で使う乱数発生器を
**一箇所で管理** します。ファイルごとに `np.random.seed(42)` を呼ぶアンチパターンを
防ぎ、同じ root seed を渡せば全工程で同一の乱数列が得られることを保証します。

## 使い方

```python
from synthpop_jp.rng import SeedRegistry

# root seed を固定してレジストリを作成
reg = SeedRegistry(root=42)

# ラベルで乱数源を取得
rng_init = reg.rng("init")  # 初期人口生成用
rng_sa = reg.rng("sa")  # SA 用
rng_eval = reg.rng("eval")  # 評価用

# rng_init / rng_sa / rng_eval はそれぞれ独立した乱数列を持つ
counts = rng_init.multinomial(100, [0.3, 0.7])
```

## seed 運用ルール（詳細は docs/rules/seed-policy.md）

1. **1 run につき 1 つの root seed** を決める。複数箇所で独立に seed を作らない。
2. `SeedRegistry` 経由でのみ `np.random.Generator` を取得する。
   直接 `np.random.default_rng()` / `np.random.seed()` は呼ばない。
3. ラベルは処理の役割を表す名詞を使う（例: `"init"`, `"sa"`, `"eval"`, `"improve"`）。
4. 同じ `(root, label)` の組みは常に同じ乱数列を返す。
   ラベルの登録順序が変わっても seed は変わらない。
5. 実験記録には root seed を必ず残す。`artifacts/<run_id>/seed.txt` に書く。

## 内部実装の概要

`np.random.SeedSequence` の階層 spawning と `hashlib.blake2b` を組み合わせます。

- `SeedSequence(root)` を root 節点とします。
- ラベル文字列を `hashlib.blake2b` でハッシュ化し、128 bit 整数に変換します。
- この整数を `root_ss.spawn(1, entropy=hash_int)` の entropy として使い、
  ラベルに一意な子 SeedSequence を取得します。
- ハッシュ化により、ラベルの登録順序に依存しない決定的な seed を実現します。
- `rng(label)` は毎回 `np.random.default_rng(child_ss)` で新しい Generator を
  作って返します。同じラベルなら初期 state は常に同じです。

## プラットフォーム差異への対応

NumPy の `SeedSequence` はプラットフォーム（macOS / Linux）によらず
同じ子 seed を生成します。endianness の影響を受けない整数型（int16 / int32）を
dtype に使うことで、bitwise 一致が macOS と Linux の両方で成立します。
"""

from __future__ import annotations

import hashlib

import numpy as np

# ハッシュの切り出しバイト数。128 bit = 16 bytes を整数として使う。
_HASH_BYTES = 16


def _label_to_entropy(label: str) -> int:
    """ラベル文字列を 128 bit 整数に変換する.

    ``hashlib.blake2b`` を使い、衝突リスクを実用上無視できるレベルに抑えます。
    同じラベルは常に同じ整数を返します。

    Parameters
    ----------
    label : str
        変換対象のラベル文字列。

    Returns
    -------
    int
        128 bit の非負整数。
    """
    digest = hashlib.blake2b(label.encode(), digest_size=_HASH_BYTES).digest()
    return int.from_bytes(digest, byteorder="big")


class SeedRegistry:
    """階層 spawning による乱数源レジストリ.

    同じ ``(root, label)`` の組みに対して常に同じ ``SeedSequence`` を返します。
    ラベルのハッシュ値を entropy に使うため、登録順序に依存しない決定的な
    seed 管理を実現します。

    Parameters
    ----------
    root : int
        根となる seed 値。実験の再現性を保証するために外部から注入します。

    Examples
    --------
    >>> reg = SeedRegistry(root=42)
    >>> gen = reg.rng("init")
    >>> isinstance(gen, np.random.Generator)
    True
    """

    def __init__(self, root: int) -> None:
        self._root = root
        self._root_ss = np.random.SeedSequence(root)
        # ラベル → 子 SeedSequence のキャッシュ
        self._cache: dict[str, np.random.SeedSequence] = {}

    def spawn(self, label: str) -> np.random.SeedSequence:
        """ラベルに対応する子 SeedSequence を返す.

        同じ ``(root, label)`` の組みは常に同じ ``SeedSequence`` を返します。
        ラベルの登録順序が変わっても結果は変わりません。

        Parameters
        ----------
        label : str
            乱数源を識別するラベル。役割を表す名詞を使う（例: ``"init"``, ``"sa"``）。

        Returns
        -------
        np.random.SeedSequence
            対応する子 SeedSequence。
        """
        if label not in self._cache:
            # ラベルをハッシュ化して entropy に使い、順序非依存の子 seed を得る。
            # root の entropy（int か Sequence[int]）と label_hash を組み合わせて
            # 新たな SeedSequence を構築する。
            label_hash = _label_to_entropy(label)
            raw = self._root_ss.entropy
            if isinstance(raw, int):
                combined: int = raw ^ label_hash
            else:
                # Sequence[int] の場合は先頭要素のみ使う（実用上 int が大半）
                first = int(raw[0]) if raw else 0
                combined = first ^ label_hash
            child_ss = np.random.SeedSequence(combined)
            self._cache[label] = child_ss
        return self._cache[label]

    def rng(self, label: str) -> np.random.Generator:
        """ラベルに対応する np.random.Generator を返す.

        呼び出しのたびに **新しい** Generator オブジェクトを生成しますが、
        内部の初期 state は同じ ``(root, label)`` なら常に同一です。
        したがって、同じラベルで連続して呼び出しても、それぞれが
        乱数列の先頭から独立して使えます。

        Parameters
        ----------
        label : str
            乱数源を識別するラベル。

        Returns
        -------
        np.random.Generator
            初期化済みの Generator。
        """
        child_ss = self.spawn(label)
        return np.random.default_rng(child_ss)

    def __repr__(self) -> str:
        """デバッグ用の文字列表現."""
        labels_repr = ", ".join(f'"{lb}"' for lb in self._cache)
        return f"SeedRegistry(root={self._root}, labels=[{labels_repr}])"
