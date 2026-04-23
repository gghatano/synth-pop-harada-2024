# task-003: 命名・LICENSE・CITATION の配置（承認済決定の反映）

## 目的

2026-04-23 にユーザー承認された「PyPI 名 `synthpop-jp` / LICENSE Apache-2.0」を、リポジトリのファイルとして物理的に反映する。以降の task がこれらの決定事項に依存するため、最優先で確定させる。

## 前提・依存

- 承認事項（memory `naming_license.md` 参照）:
  - PyPI / CLI 名: `synthpop-jp`
  - import 名: `synthpop_jp`
  - LICENSE: Apache-2.0
  - 引用: `CITATION.cff` に Murata 2017 + Harada 2024 を preferred-citation、Zenodo DOI は v0.1 公開時
- task-004（pyproject.toml）と task-006（README）は本タスクの決定を引き継ぐ。

## 成果物

### a. `/LICENSE`

Apache-2.0 全文（SPDX 識別子 `Apache-2.0`、著作権表記は著者名と年のみ）。

### b. `/NOTICE`

依存ライブラリ（pandas, numpy, scipy, scikit-learn, pydantic, typer, matplotlib, pyyaml, rich 他）のライセンスクレジット骨子。Phase 1 で最終化。

### c. `/CITATION.cff`

骨子:
```yaml
cff-version: 1.2.0
title: "synthpop-jp"
message: "If you use this software, please cite it as below."
authors: [] # Phase 0 中にユーザー確認
repository-code: "https://github.com/<owner>/synth-pop-harada-2024"
version: "0.0.0-dev"
license: Apache-2.0
preferred-citation:
  type: article
  authors: []
  title: "Murata 2017 / Harada 2024 のタイトルを Phase 0 中に確認して記入"
  # DOI は Zenodo 発行後に追記
```

### d. `/DATASET.md`

- `data/sample_case/` は完全合成ダミーである旨の宣言
- e-Stat 実データは再配布しない、`scripts/fetch_estat.py` でユーザー環境取得
- 統計法 §44 および e-Stat 利用規約の出典表記義務
- 合成データのライセンス扱い（Apache-2.0 配下、データは研究用途限定の注記）

### e. `/CHANGELOG.md`

Keep a Changelog 形式、`[Unreleased]` セクションのみでスタート。SemVer 方針を冒頭に明記し、v0.x 中は破壊的変更を許容する旨を記載。

### f. `/CODE_OF_CONDUCT.md`

Contributor Covenant v2.1 をそのまま採用。

### g. `docs/adr/0004-naming-and-license.md`

本決定の根拠記録（ADR テンプレは task-008 で統一）。

## 受け入れ基準

- 上記 7 ファイルがリポジトリに存在する。
- `LICENSE` が Apache-2.0 の正規テキストで、改変なし（SPDX ツールでパース可）。
- `CITATION.cff` が `cffconvert --validate` で通る形式。
- `DATASET.md` に e-Stat 再配布禁止と出典表記義務が明記されている。
- `CHANGELOG.md` の冒頭が `# Changelog` と `This project adheres to Semantic Versioning.` を含む。

## 推定規模

S（1〜2 時間）。主に定形ファイルの配置。

## 参照

- memory `naming_license.md`（承認済決定の一次記録）
- `docs/reviews/review-oss.md` 指摘 1, 2, 3, 12
- `docs/reviews/action-plan.md` §1.3
