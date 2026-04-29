"""Tests for io/synthesized.py — synthetic CSV reconstruction (Issue #59)."""

from __future__ import annotations

import csv
from pathlib import Path

from synthpop_jp.io.synthesized import reconstruct_population_arrays_from_persons_csv


def _write_persons_csv(path: Path, rows: list[dict[str, object]]) -> None:
    """Write a small persons CSV at ``path`` for tests."""
    fieldnames = ["person_id", "household_id", "family_type", "role", "sex", "age"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


class TestReconstructPopulationArrays:
    """reconstruct_population_arrays_from_persons_csv の単体テスト."""

    def test_reconstructs_basic_household(self, tmp_path: Path) -> None:
        """1 世帯 3 人の CSV を再構築し、属性が一致する."""
        csv_path = tmp_path / "synthetic_persons.csv"
        _write_persons_csv(
            csv_path,
            [
                {
                    "person_id": "P_000001",
                    "household_id": "HH_000001",
                    "family_type": "couple_and_children",
                    "role": "father",
                    "sex": "M",
                    "age": 40,
                },
                {
                    "person_id": "P_000002",
                    "household_id": "HH_000001",
                    "family_type": "couple_and_children",
                    "role": "mother",
                    "sex": "F",
                    "age": 38,
                },
                {
                    "person_id": "P_000003",
                    "household_id": "HH_000001",
                    "family_type": "couple_and_children",
                    "role": "child",
                    "sex": "M",
                    "age": 10,
                },
            ],
        )
        arrays = reconstruct_population_arrays_from_persons_csv(csv_path)
        assert arrays.n_persons == 3
        # ages 40, 38, 10 が含まれる
        assert sorted(int(a) for a in arrays.age) == [10, 38, 40]
        # all in household 1
        assert all(int(h) == 1 for h in arrays.household_id)

    def test_multi_household_count(self, tmp_path: Path) -> None:
        """複数世帯を再構築すると人数と世帯数が CSV と一致する."""
        csv_path = tmp_path / "synthetic_persons.csv"
        rows: list[dict[str, object]] = []
        person_id = 1
        for hh in range(1, 4):
            for role, sex, age in [("husband", "M", 35), ("wife", "F", 33)]:
                rows.append(
                    {
                        "person_id": f"P_{person_id:06d}",
                        "household_id": f"HH_{hh:06d}",
                        "family_type": "couple",
                        "role": role,
                        "sex": sex,
                        "age": age,
                    }
                )
                person_id += 1
        _write_persons_csv(csv_path, rows)
        arrays = reconstruct_population_arrays_from_persons_csv(csv_path)
        assert arrays.n_persons == 6
        # 3 世帯
        assert len(set(int(h) for h in arrays.household_id)) == 3

    def test_registers_unique_family_types_and_roles(self, tmp_path: Path) -> None:
        """family_type / role は CSV 内の出現名がすべて Registry に登録される."""
        csv_path = tmp_path / "synthetic_persons.csv"
        _write_persons_csv(
            csv_path,
            [
                {
                    "person_id": "P_000001",
                    "household_id": "HH_000001",
                    "family_type": "single",
                    "role": "single",
                    "sex": "M",
                    "age": 30,
                },
                {
                    "person_id": "P_000002",
                    "household_id": "HH_000002",
                    "family_type": "couple",
                    "role": "husband",
                    "sex": "M",
                    "age": 35,
                },
                {
                    "person_id": "P_000003",
                    "household_id": "HH_000002",
                    "family_type": "couple",
                    "role": "wife",
                    "sex": "F",
                    "age": 33,
                },
            ],
        )
        arrays = reconstruct_population_arrays_from_persons_csv(csv_path)
        # FamilyTypeRegistry has both "single" and "couple"
        assert arrays.family_reg.id_of("single") >= 0
        assert arrays.family_reg.id_of("couple") >= 0
        # RoleRegistry has all 3
        assert arrays.role_reg.id_of("single") >= 0
        assert arrays.role_reg.id_of("husband") >= 0
        assert arrays.role_reg.id_of("wife") >= 0
