# synthpop-jp (English)

A Python re-implementation of the Simulated Annealing-based synthetic population generator of Murata et al. (2017), extended with the utility/disclosure-risk evaluation axes (including ARD) proposed by Harada (2024) and a **generate → evaluate → improve** loop. Intended for research use.

[日本語 README](./README.md)

> **Status**: Phase 0 skeleton. The full English README body will be completed by v0.1 (Phase 2). The sections below describe the intended structure.

---

## 1. What it does (3 lines)

- Generates internally-consistent synthetic household/person microdata **only from publicly available census aggregate tables**.
- Produces a three-layer evaluation report (statistical consistency, utility, disclosure risk) for every synthetic population.
- Explores generation parameters with an improvement loop (rule-based / Pareto) to find "useful" synthetic populations.

*(Full body: v0.1)*

---

## 2. Positioning — Murata 2017 and Harada 2024

Two papers are bundled into one Python toolkit:

- **Generation side** — Murata et al. (2017): SA-based synthetic population generation from aggregate tables.
- **Evaluation side** — Harada (2024): utility and disclosure-risk axes for virtual-city synthetic data, notably the **ARD (Attribute Risk Distance)** metric.

*(Full body: v0.1)*

---

## 3. Installation

```bash
uv tool install synthpop-jp
# or
uvx synthpop-jp --help
```

*(Full body: v0.1)*

---

## 4. 30-second Quickstart

*(Works after Phase 1 completion.)*

```bash
uvx synthpop-jp quickstart
```

*(Full body: v0.1)*

---

## 5. Input / Output

Inputs are a set of aggregate-table CSVs; outputs are synthetic household/person CSVs plus an evaluation report. See [`docs/spec/spec.md`](docs/spec/spec.md) §7 for column-level details.

*(Full body: v0.1)*

---

## 6. Comparison to related OSS

| Tool | Data assumption | Method | Difference from this project |
|---|---|---|---|
| synthpop (R) | Sample microdata required | CART / conditional probability | Aggregate tables only |
| SDV / CTGAN | General tabular data | GAN / copula | Preserves household structure via SA |
| PopulationSim / ActivitySim | Travel demand | IPF | Customizable SA objective |
| **synthpop-jp** | Public aggregates only | SA (Murata 2017) | Japanese census templates + ARD evaluation |

*(Full body: v0.1)*

---

## 7. Citation

Please cite both the software and the underlying papers. See [`CITATION.cff`](CITATION.cff) for BibTeX.

- Software: `CITATION.cff` (GitHub "Cite this repository" button)
- Generation method: Murata et al. (2017)
- Evaluation method: Harada (2024)

*(Full body: v0.1)*

---

## 8. Roadmap (summary)

- **v0.1 (alpha)** — Phase 2 complete. `synthpop-jp quickstart` runs in 10 s on bundled dummy data.
- **v0.2** — Phase 4. age-swap / hybrid transitions, ARD-based evaluation, e-Stat adapter, mkdocs site.
- **v0.3** — Phase 5. Improvement loop (rule_based / Pareto), plugin entry_points.
- **v1.0** — Paper release. Frozen `paper_results/`, Zenodo DOI, full English docs.

See [`docs/reviews/action-plan.md`](docs/reviews/action-plan.md) §3.

---

## 9. Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for setup and the Issue-driven workflow.
The project follows the [Contributor Covenant v2.1](CODE_OF_CONDUCT.md).

*(Full body: v0.1)*

---

## 10. License

[Apache License 2.0](LICENSE). Dependency credits: [`NOTICE`](NOTICE). Dataset handling policy (e-Stat redistribution, synthetic-dummy scope, Japanese Statistics Act §44): [`DATASET.md`](DATASET.md).
