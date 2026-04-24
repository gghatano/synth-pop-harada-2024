"""決定性回帰テスト.

同じ seed を渡すと bitwise 一致の出力が得られることを検証します。

## テスト対象

1. ``SeedRegistry`` の決定性（単体）
2. ``scripts/generate_sample_case.py`` の bitwise 一致（sha256 比較）

Issue #16 の成功条件「同 seed で bitwise 一致」を CI の regression guard として実装します。
SA 決定性（Phase 2）や評価器決定性（Phase 3.5）はスコープ外のため、ここでは触りません。
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from synthpop_jp.rng import SeedRegistry

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parents[4]
_GENERATE_SCRIPT = _REPO_ROOT / "scripts" / "generate_sample_case.py"
_SAMPLE_CASE_DIR = _REPO_ROOT / "data" / "sample_case"

_SAMPLE_CASE_FILES = [
    "family_type_counts.csv",
    "children_count_dist.csv",
    "demographic_by_age_sex.csv",
    "age_diff_parent_child.csv",
    "age_diff_couple.csv",
    "demographic_by_family_type_role.csv",
    "household_size_by_family_type.csv",
]


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    """ファイルの SHA-256 ハッシュを文字列で返す."""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _run_generate(output_dir: Path) -> None:
    """generate_sample_case.py を output_dir に向けて実行する."""
    result = subprocess.run(
        [sys.executable, str(_GENERATE_SCRIPT), "--output-dir", str(output_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"generate_sample_case.py failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )


# ---------------------------------------------------------------------------
# Cycle 1 補完: SeedRegistry の決定性（integration 寄りの確認）
# ---------------------------------------------------------------------------


class TestSeedRegistryDeterminism:
    """SeedRegistry が issue #16 の成功条件を満たすことを確認する."""

    def test_same_root_same_label_bitwise_equal_samples(self) -> None:
        """同じ (root, label) で生成した乱数配列が bitwise 一致する."""
        reg1 = SeedRegistry(root=42)
        reg2 = SeedRegistry(root=42)

        arr1 = reg1.rng("init").integers(0, 10000, size=1000)
        arr2 = reg2.rng("init").integers(0, 10000, size=1000)

        np.testing.assert_array_equal(arr1, arr2)

    def test_init_sa_bitwise_different(self) -> None:
        """'init' と 'sa' は同じ root でも異なる乱数列を生成する."""
        reg = SeedRegistry(root=42)

        arr_init = reg.rng("init").integers(0, 10000, size=1000)
        arr_sa = reg.rng("sa").integers(0, 10000, size=1000)

        assert not np.array_equal(arr_init, arr_sa), (
            "'init' と 'sa' の乱数列が一致した（seed 分離が失敗している）"
        )

    def test_multinomial_bitwise_equal(self) -> None:
        """multinomial のような用途でも bitwise 一致する（generate_sample_case の手本）."""
        probs = np.array([0.15, 0.20, 0.30, 0.05, 0.08, 0.05, 0.05, 0.07, 0.05])

        reg1 = SeedRegistry(root=42)
        reg2 = SeedRegistry(root=42)

        result1 = reg1.rng("init").multinomial(100, probs)
        result2 = reg2.rng("init").multinomial(100, probs)

        np.testing.assert_array_equal(result1, result2)


# ---------------------------------------------------------------------------
# Cycle 4: generate_sample_case.py の bitwise 一致 regression guard
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestGenerateSampleCaseBitwiseEqual:
    """``scripts/generate_sample_case.py`` を 2 回実行して SHA-256 一致を確認する.

    Issue #12 で確立した「seed=42 で 2 回実行すると bitwise 一致」の挙動を
    回帰テストとして保護します。

    Notes
    -----
    スクリプトは ``data/sample_case/`` に直接書き込むため、実行前後でファイルが
    存在することが前提です。テスト用一時ディレクトリに書き込む方式を採用しています。
    """

    def test_generate_twice_sha256_identical(self, tmp_path: Path) -> None:
        """2 回生成した CSV の SHA-256 が全ファイルで一致する."""
        run1_dir = tmp_path / "run1"
        run2_dir = tmp_path / "run2"

        _run_generate(run1_dir)
        _run_generate(run2_dir)

        for filename in _SAMPLE_CASE_FILES:
            path1 = run1_dir / filename
            path2 = run2_dir / filename

            assert path1.exists(), f"run1 に {filename} が存在しない"
            assert path2.exists(), f"run2 に {filename} が存在しない"

            sha1 = _sha256(path1)
            sha2 = _sha256(path2)

            assert sha1 == sha2, (
                f"{filename}: 2 回の生成結果が一致しない\n"
                f"  run1 sha256: {sha1}\n"
                f"  run2 sha256: {sha2}"
            )

    def test_generate_matches_committed_data(self) -> None:
        """コミット済みの data/sample_case/ と新規生成の SHA-256 が一致する.

        既存の data/sample_case/ が存在しない場合はスキップします。
        """
        if not _SAMPLE_CASE_DIR.exists():
            pytest.skip("data/sample_case/ が存在しないためスキップ")

        missing = [f for f in _SAMPLE_CASE_FILES if not (_SAMPLE_CASE_DIR / f).exists()]
        if missing:
            pytest.skip(f"data/sample_case/ に不足ファイルあり: {missing}")

        import tempfile

        with tempfile.TemporaryDirectory() as td:
            fresh_dir = Path(td) / "fresh"
            _run_generate(fresh_dir)

            for filename in _SAMPLE_CASE_FILES:
                committed = _SAMPLE_CASE_DIR / filename
                fresh = fresh_dir / filename

                sha_committed = _sha256(committed)
                sha_fresh = _sha256(fresh)

                assert sha_committed == sha_fresh, (
                    f"{filename}: コミット済みデータと新規生成が一致しない\n"
                    f"  committed sha256: {sha_committed}\n"
                    f"  fresh    sha256:  {sha_fresh}\n"
                    "  → numpy バージョンが変わったか、スクリプトが変更された可能性があります。"
                )
