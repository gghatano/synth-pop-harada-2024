# Architecture Decision Records (ADR)

本ディレクトリは `synthpop-jp` の **構造的な設計決定** を記録する。一度決めたら蒸し返されがちな論点を、後から根拠付きで参照できるように凍結する。

## 書式

各 ADR は Michael Nygard 形式（Status / Context / Decision / Consequences）に従い、以下のセクションを持つ。

1. **タイトル**: `NNNN-kebab-case-title`（例: `0001-internal-representation.md`）
2. **Status**: `Proposed` | `Accepted` | `Superseded by NNNN` | `Deprecated`
3. **Date**: `YYYY-MM-DD`
4. **Context**: この決定が必要になった背景。レビュー指摘や性能要件など。
5. **Decision**: 何を決めたか。具体的な選択肢と、選ばれた選択肢。
6. **Consequences**: 何が楽になり、何が苦しくなるか。
7. **References**: 出典（レビュー指摘の逆参照、論文、Issue、PR 等）。

## 番号付け規約

- ゼロ埋め 4 桁の連番（`0001`, `0002`, ...）
- 欠番は作らない
- ファイル名は `NNNN-kebab-case-title.md`

## Superseded 運用

- 既存 ADR を上書きしない
- 代わりに新しい ADR（`NNNN+k`）を作り、古い ADR の **Status を `Superseded by NNNN+k` に更新**する
- 新 ADR の **References に旧 ADR を明記**する
- これにより「いつ・なぜ方針が変わったか」を時系列で追える

## 現在の ADR 一覧

| No. | Title | Status | Date |
|---|---|---|---|
| 0001 | [Internal Representation (NumPy parallel arrays + diff update)](0001-internal-representation.md) | Accepted | 2026-04-23 |
| 0002 | [Objective Function Normalization (two modes)](0002-objective-normalization.md) | Accepted | 2026-04-23 |
| 0003 | [Privacy Evaluation Layers (proxy / CAP / MIA)](0003-privacy-evaluation-layers.md) | Accepted | 2026-04-23 |
| 0004 | [Naming and License (synthpop-jp / Apache-2.0)](0004-naming-and-license.md) | Accepted | 2026-04-23 |

## 新しい ADR を書くとき

1. 本 README に行を追加
2. `docs/adr/NNNN-title.md` を作成（既存 ADR をテンプレにする）
3. Status は作成時は `Proposed`、レビュー完了後 `Accepted`
4. コード/仕様上で関連する位置から `ADR-NNNN` で逆参照する
