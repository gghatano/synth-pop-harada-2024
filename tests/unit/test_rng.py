"""Unit tests for SeedRegistry.

TDD: tests are written before the implementation.
"""

from __future__ import annotations

import numpy as np
import pytest

from synthpop_jp.rng import SeedRegistry

# ---------------------------------------------------------------------------
# Cycle 1: 決定性 — 同 root + 同 label → 同 SeedSequence
# ---------------------------------------------------------------------------


class TestSeedDeterminism:
    """同じ (root, label) は常に同じ SeedSequence を返す."""

    def test_same_root_same_label_returns_same_seed(self) -> None:
        """同じ root と label を渡すと毎回同じ SeedSequence を返す."""
        reg1 = SeedRegistry(root=42)
        reg2 = SeedRegistry(root=42)

        seq1 = reg1.spawn("init")
        seq2 = reg2.spawn("init")

        # SeedSequence は直接比較できないため state を比較する
        assert seq1.state == seq2.state

    def test_same_registry_spawn_twice_returns_same_seed(self) -> None:
        """同一レジストリで同じラベルを 2 回呼んでも同じ SeedSequence."""
        reg = SeedRegistry(root=42)

        seq1 = reg.spawn("init")
        seq2 = reg.spawn("init")

        assert seq1.state == seq2.state

    def test_different_root_returns_different_seed(self) -> None:
        """異なる root では異なる SeedSequence を返す."""
        reg1 = SeedRegistry(root=42)
        reg2 = SeedRegistry(root=99)

        seq1 = reg1.spawn("init")
        seq2 = reg2.spawn("init")

        assert seq1.state != seq2.state


# ---------------------------------------------------------------------------
# Cycle 2: ユニーク性 — 異なる label → 異なる SeedSequence
# ---------------------------------------------------------------------------


class TestSeedUniqueness:
    """異なるラベルは異なる SeedSequence を返す."""

    def test_different_labels_return_different_seeds(self) -> None:
        """同じ root でも label が違えば SeedSequence が異なる."""
        reg = SeedRegistry(root=42)

        seq_init = reg.spawn("init")
        seq_sa = reg.spawn("sa")
        seq_eval = reg.spawn("eval")

        assert seq_init.state != seq_sa.state
        assert seq_sa.state != seq_eval.state
        assert seq_init.state != seq_eval.state

    def test_spawn_order_independent(self) -> None:
        """ラベルを登録する順序が変わっても、同 (root, label) の seed は変わらない."""
        reg_forward = SeedRegistry(root=42)
        _ = reg_forward.spawn("init")
        _ = reg_forward.spawn("sa")
        _ = reg_forward.spawn("eval")

        reg_reverse = SeedRegistry(root=42)
        _ = reg_reverse.spawn("eval")
        _ = reg_reverse.spawn("sa")
        seq_eval_reverse = reg_reverse.spawn("init")

        # init の state は順序によらず同一であるべき
        reg_ref = SeedRegistry(root=42)
        seq_init_ref = reg_ref.spawn("init")

        assert seq_eval_reverse.state == seq_init_ref.state

    def test_many_labels_all_unique(self) -> None:
        """複数のラベルをまとめて登録しても、すべて異なる SeedSequence になる."""
        reg = SeedRegistry(root=42)
        labels = ["init", "sa", "eval", "improve", "benchmark"]
        sequences = [reg.spawn(label) for label in labels]

        states = [seq.state for seq in sequences]
        # すべて異なることを確認
        assert len(states) == len(set(str(s) for s in states))


# ---------------------------------------------------------------------------
# Cycle 3: rng() — np.random.Generator を返し、同ラベルで同一初期状態
# ---------------------------------------------------------------------------


class TestSeedRegistryRng:
    """rng(label) は同じ label に対して同じ初期状態の Generator を返す."""

    def test_rng_returns_generator(self) -> None:
        """`rng` の戻り値が np.random.Generator であることを確認."""
        reg = SeedRegistry(root=42)
        gen = reg.rng("init")
        assert isinstance(gen, np.random.Generator)

    def test_rng_same_label_same_initial_state(self) -> None:
        """同じ label で rng() を 2 回呼ぶと同じ乱数列を生成する."""
        reg1 = SeedRegistry(root=42)
        reg2 = SeedRegistry(root=42)

        gen1 = reg1.rng("init")
        gen2 = reg2.rng("init")

        # 乱数列が一致することで初期状態が同じであることを検証
        samples1 = gen1.integers(0, 1000, size=10)
        samples2 = gen2.integers(0, 1000, size=10)

        np.testing.assert_array_equal(samples1, samples2)

    def test_rng_different_labels_different_sequences(self) -> None:
        """異なる label の rng() は異なる乱数列を生成する."""
        reg = SeedRegistry(root=42)

        gen_init = reg.rng("init")
        gen_sa = reg.rng("sa")

        samples_init = gen_init.integers(0, 1000, size=10)
        samples_sa = gen_sa.integers(0, 1000, size=10)

        # 確率的にほぼ必ず異なる（同一の確率は 1/1000^10 以下）
        assert not np.array_equal(samples_init, samples_sa)

    def test_rng_each_call_returns_fresh_generator(self) -> None:
        """同一レジストリで同じ label を 2 回呼ぶと、それぞれ新しい Generator を返す."""
        reg = SeedRegistry(root=42)

        gen_a = reg.rng("init")
        # 1 回目の Generator から数値を消費する
        _ = gen_a.integers(0, 100, size=5)

        # 2 回目の呼び出しは初期状態から始まる新しい Generator
        gen_b = reg.rng("init")
        first_from_b = gen_b.integers(0, 100, size=5)

        # gen_a と gen_b の最初の 5 個は同じはず（初期状態が等しい）
        gen_c = reg.rng("init")
        first_from_c = gen_c.integers(0, 100, size=5)

        np.testing.assert_array_equal(first_from_b, first_from_c)


# ---------------------------------------------------------------------------
# Cycle 2 追加: Cycle 2 の spawn_order_independent テストの補足
# ---------------------------------------------------------------------------


class TestSeedRegistryIndexStability:
    """ラベルの登録順序と index 安定性の詳細確認."""

    def test_first_label_index_stable_regardless_of_later_additions(self) -> None:
        """最初に登録したラベルの seed は、後から別ラベルが追加されても変わらない."""
        reg_a = SeedRegistry(root=42)
        seq_init_only = reg_a.spawn("init")

        reg_b = SeedRegistry(root=42)
        seq_init_then_sa = reg_b.spawn("init")
        _seq_sa = reg_b.spawn("sa")

        # init の seed は sa の追加後も変わらない
        assert seq_init_only.state == seq_init_then_sa.state

    def test_repr_contains_root(self) -> None:
        """`repr` に root 値が含まれる（デバッグ容易性の確認）."""
        reg = SeedRegistry(root=42)
        assert "42" in repr(reg)

    @pytest.mark.parametrize("root", [0, 1, 42, 12345, 2**31 - 1])
    def test_various_roots_produce_deterministic_seeds(self, root: int) -> None:
        """さまざまな root 値で決定性が保たれる."""
        reg1 = SeedRegistry(root=root)
        reg2 = SeedRegistry(root=root)
        assert reg1.spawn("init").state == reg2.spawn("init").state
