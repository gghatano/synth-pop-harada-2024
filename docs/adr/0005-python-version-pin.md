# ADR-0005: サポート Python バージョンを 3.12 に固定する

## Status

Accepted — 2026-04-23

## Context

Phase 0 の当初 scaffolding（PR #5）では `requires-python = ">=3.11"` とし、CI も Python 3.11 / 3.12 の matrix 構成にしていた。これは OSS として採用の裾野を広げる意図だったが、次の 3 点で本プロジェクトには過剰だった。

1. 本リポジトリは研究プロトタイプであり、外部 contributor の想定母数は大きくない。
2. Python 3.11 と 3.12 で `numpy` / `scipy` / `pydantic` の挙動差はごく軽微だが、CI 時間は 2 倍、issue 発生時の切り分けコストは倍になる。
3. contributor の手元 venv が 3.11 か 3.12 かで `pyright` の診断がわずかに変わる実例があり、「環境差異のトラブル回避」が優先度の高い要件として確認された（2026-04-23 の対話で確定）。

`docs/reviews/review-oss.md` が指摘した採用促進の観点はあるが、現フェーズでは「技術者が `requires-python` 1 行で動作条件を判断できる明快さ」を優先する。

## Decision

- `pyproject.toml` の `requires-python = "==3.12.*"` として Python 3.12 系に固定する。
- `[tool.ruff] target-version = "py312"`、`pyrightconfig.json` の `pythonVersion = "3.12"` も同期。
- `.github/workflows/ci.yml` は matrix を撤去し、Python 3.12 単一ジョブとする。
- `docs/spec/spec.md` §6.1 の「Python 3.11+」を「Python 3.12（固定）」に改め、本 ADR を参照させる。
- 3.13 / 3.14 への引き上げは、本リポで実用する外部依存（`numpy`, `scipy`, `scikit-learn`）が 3.13+ を stable リリースで正式サポートしたタイミングで再評価する。再評価は新規 ADR で行う。

## Consequences

### Positive

- CI 時間が ~50% 短縮される（matrix 2 ジョブ → 1 ジョブ）。
- 開発環境の挙動がすべて同一 Python minor に揃い、切り分け時間が減る。
- 将来 Phase 2〜4 で SA コアの性能最適化を行う際、`PEP 669` (monitoring API) や `PEP 667` (frame scope) など 3.12 固有機能を前提にできる。

### Negative

- Python 3.11 のみ利用可能な外部環境（古い JupyterHub / 研究機関の共有サーバ）では `uv tool install synthpop-jp` / `pip install synthpop-jp` が拒否される。PyPI 上での採用率に影響しうる。
- 将来 3.11 が EOL になる前に 3.12 が EOL になる可能性は低いが、いずれにせよ Python リリースサイクルに追従して本 ADR を更新する必要がある。

### Mitigation

- CLAUDE.md / README / CONTRIBUTING に Python 3.12 前提であることを明記する。
- Phase 1 以降の CI に `pip install --python 3.11` テストは入れない（失敗が仕様）。

## References

- `docs/reviews/review-oss.md` 指摘 4, 7
- `docs/reviews/action-plan.md` §2C
- Issue #7, PR #7 相当（本変更）
- ADR-0004（命名・LICENSE）：本 ADR と独立だが同時期の運用方針決定
