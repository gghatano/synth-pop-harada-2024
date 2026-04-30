# synthpop-jp Documentation

A Python research prototype that combines **synthetic population generation** following Murata et al. (2017) with the **evaluation framework** of Harada (2024).

## What it does

- Generates internally-consistent synthetic households and persons **using only public Census tabulations**
- Auto-generates evaluation reports across **three layers**: statistical consistency, utility, and privacy
- Explores improvement loops over generation parameters (`rule_based` / Pareto, planned for Phase 5)

## Where to start

1. **[Development workflow](getting-started/development-workflow.md)** — overall development flow
2. **[How it works](guides/how-it-works.md)** — SA, transitions, objective, evaluators (Japanese; EN overview at [how-it-works.en.md](guides/how-it-works.en.md))
3. **[Progress overview](reports/2026-04-30-progress-overview.md)** — current status

## Contributing

See the [rules](rules/issue-driven-development.md) directory for issue-driven development, TDD, and git worktree conventions.

## Specification and evaluation

- [Spec](spec/spec.md) — full specification
- [Metrics](spec/metrics.md) — broad / narrow utility, three privacy layers
- [MIA Protocol](spec/mia_protocol.md) — pre-registration for Phase 5 MIA implementation
- [Experiment report format](spec/experiment_report_format.md) — schema for experiment records

## 日本語

[Home (JA)](index.md) を参照してください。
