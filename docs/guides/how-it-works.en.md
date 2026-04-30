# How it works (overview, English)

This is an English summary of the Japanese full version at [`how-it-works.md`](how-it-works.md). For details (formulas, code paths, CLI flags), refer to the Japanese version.

## 1. The big picture

`synthpop-jp` does three things, all driven from a single CLI:

- **Generate** synthetic households and persons from public statistics (no microdata required)
- **Anneal** (refine) the generation result with Simulated Annealing (SA) to minimize errors against target statistics
- **Evaluate** the result on three independent axes: statistical consistency, utility, and privacy

## 2. Generation

Inputs (CSV files in `data/sample_case/`):

- `family_type_counts.csv` — household counts by family type
- `household_size_by_family_type.csv` — size distribution per family type
- `demographic_by_age_sex.csv` — overall age × sex pyramid
- `demographic_by_family_type_role.csv` — fine-grained age × sex by (family_type, role)
- `age_diff_couple.csv`, `age_diff_parent_child.csv` — relational statistics

The generator constructs households with the right composition and assigns ages either by weighted random sampling (default) or by Largest Remainder for zero F-W error (Murata 2017 §3, optional flag).

## 3. Refinement (SA)

Once an initial population is built, SA repeatedly proposes small changes (age-change, age-swap, or hybrid mix), accepts them by Metropolis criterion, and tracks the best score. The objective is the L1 sum across 5 base statistics plus optional family_type × sex pyramids (15 stats by default; 21-stat full coverage is in progress).

The implementation uses delta updates: each iteration runs in O(1) with respect to population size, achieving 1.5 µs / step on a 1,000-household problem (67× the 100 µs target).

## 4. Evaluation

Three independent axes:

- **Statistical consistency** (`aggregate.l1.*`): per-statistic L1 error, Murata-style breakdown
- **Utility** (`broad_utility.*`, `narrow_utility.*`): mixed-type correlation, joint TV, and TSTR/TRTS for 3 fixed downstream tasks
- **Privacy** (`rare_cell.*`, `cap.*`, `dcr.*`, `nndr.*`, `ard.*`, `mia.*`): rare cell monitoring, attribute inference (CAP/TCAP), distance proxies (DCR/NNDR/ARD), shadow MIA (Phase 5)

Each evaluator writes flat keys to `metrics.json`. The Markdown renderer (`reports/markdown.py`) auto-includes citations for each metric prefix and a license section if `provenance.json` is present.

## 5. CLI surface

```bash
synthpop-jp quickstart                         # 1-shot demo
synthpop-jp generate --config foo.yaml          # full pipeline
synthpop-jp evaluate --real-persons-csv real.csv  # all evaluators
synthpop-jp compare config_a.yaml config_b.yaml --seeds 10  # n-seed comparison
```

For details and the full configuration schema, see the Japanese version of this document and `docs/spec/spec.md`.
