# ADR-0004: 命名 `synthpop-jp` とライセンス Apache-2.0

- **Status**: Accepted（ユーザー承認: 2026-04-23）
- **Date**: 2026-04-23

## Context

旧版では命名が三重にズレていた（`docs/reviews/review-oss.md` 指摘 1）。

- リポジトリ名: `synth-pop-harada-2024`
- `docs/spec/spec.md` 旧版 §9 のパッケージ名: `synthetic_population`
- CLI エントリ: `python -m synthetic_population.cli ...`（30 文字超、Quickstart に不向き）
- PyPI 公開時の名前: 未定義

このズレを放置すると:

- PyPI の一般語（`synthetic_population`）は類似 OSS（`synthpop` R パッケージ、`SDV`、`pop-synth`、`SynPop` 等）に埋もれ Googleable でない
- リポジトリ名の "harada-2024" は Harada 2024 論文を想起させるが、旧 spec 本文は Murata 2017 中心で Harada への言及ゼロ → 読者が「どちらの論文の実装か」判断できない
- 引用時に `synthetic_population` だけでは DOI や論文参照に耐えない

ライセンス面では、旧 §20 に LICENSE が無く、依存ライブラリ（pandas / scipy / scikit-learn 等）のライセンス整合も未記載だった（OSS 指摘 2）。e-Stat 再配布規約への対応も書かれていなかった。

## Decision

### 命名（ユーザー承認済み 2026-04-23、動かさない）

- **PyPI パッケージ名**: `synthpop-jp`
- **import 名**: `synthpop_jp`（PEP 8 準拠、ハイフン不可のため）
- **CLI エントリポイント**: `synthpop-jp`（`[project.scripts]` に登録、`uvx synthpop-jp ...` で起動可）
- **リポジトリ名**: `synth-pop-harada-2024`（現状維持、研究期間中の実験リポ名として許容）
- **spec §9 のディレクトリ**: `src/synthpop_jp/...`
- **README 冒頭に必須の一文**: "A Python re-implementation of Murata et al. (2017) synthetic population generator, with usability/privacy evaluation following Harada et al. (2024)"

### ライセンス（ユーザー承認済み 2026-04-23）

- **Apache-2.0** を採用
  - 研究ユーザー向けに**特許条項による保護**が重要
  - 依存ライブラリ（pandas BSD-3、numpy BSD、scipy BSD、pydantic MIT、typer MIT、scikit-learn BSD）と互換
  - GPL 系には依存しない（CI で license 互換チェック）
- `LICENSE`（Apache-2.0 全文）と `NOTICE`（依存クレジット）をリポジトリルートに配置

### データ取扱い方針

- **`data/sample_case/` は完全合成ダミー**（`scripts/generate_sample_case.py` で seed 固定生成）
- e-Stat 実データは**同梱しない**。取得スクリプト `scripts/fetch_estat.py` のみを同梱し、ユーザー環境でダウンロードさせる
- 出典表記は `io/writers.py` が `report.md` に自動埋込（統計法 §44・e-Stat 利用規約対応）
- 詳細は `DATASET.md` で管理

### 引用 (Citation)

- `CITATION.cff` に preferred-citation として **Murata 2017 と Harada 2024 を両方**記載
- v0.1 公開時に **Zenodo 連携**で DOI を発行、v1.0 で論文 DOI と並記

## Consequences

### 肯定的な結果

- **検索性**: `synthpop-jp` は PyPI 上で未使用（事前確認済）、"jp" suffix で日本の国勢調査特化を明示
- **Quickstart UX**: `uvx synthpop-jp quickstart` で 30 秒 end-to-end
- **引用耐性**: DOI + preferred-citation で研究利用者が正しく cite できる
- **ライセンス互換**: Apache-2.0 により企業研究者も特許条項で保護される
- **e-Stat 規約遵守**: 実データ非同梱 + 自動出典埋込で統計法 §44 の出典表示義務を満たす

### 否定的な結果

- **ユーザー混乱リスク**: リポジトリ名 `synth-pop-harada-2024` とパッケージ名 `synthpop-jp` が異なる
  - 緩和策: README 冒頭とドキュメントサイトで**必ずこの関係を明示**する
- **改名コスト**: 現時点では旧名 `synthetic_population` を使ったコードが無いため低コスト。Phase 1 着手前に確定したため手戻りなし
- **Apache-2.0 の形式要件**: ファイルヘッダ推奨（強制ではない）、`NOTICE` の維持義務

### SemVer と破壊的変更ポリシー

- v0.x の間は破壊的変更を許容する旨を `CHANGELOG.md` に明示
- 命名（`synthpop-jp` / `synthpop_jp` / `synthpop-jp` CLI）と LICENSE は v1.0 以降も変更しない（本 ADR を Superseded にしない限り）

## References

- レビュー指摘の逆参照:
  - `docs/reviews/review-oss.md` 指摘 1（命名ズレ）
  - `docs/reviews/review-oss.md` 指摘 2（LICENSE / e-Stat）
  - `docs/reviews/review-oss.md` 指摘 3（Harada 2024 の位置付け）
- `docs/reviews/action-plan.md` §1.3「命名の確定」、§2A「§6」
- ユーザー承認: 2026-04-23（本 worktree への作業依頼時）
- `docs/spec/spec.md` §6、§9、§17、§20
- `docs/assumptions.md`（e-Stat 利用規約の取扱い）
- 関連 ADR: なし（本 ADR と独立）
