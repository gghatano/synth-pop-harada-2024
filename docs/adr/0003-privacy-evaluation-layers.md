# ADR-0003: 秘匿性評価は 3 層（proxy / CAP baseline / shadow-based MIA）

- **Status**: Accepted
- **Date**: 2026-04-23

## Context

`docs/spec/spec.md` 旧版 §13.3 は秘匿性評価として DCR / NNDR / ARD / レコード一致率 / 属性部分一致率 を初期実装に並べ、TAPAS / MIA / AIA を「拡張候補」に置いていた。この構成には 3 つの問題がある。

1. **類似度ベース指標の既知バイアス**（`docs/reviews/review-privacy.md` 指摘 2）: Ganev & De Cristofaro (2024) "On the Inadequacy of Similarity-based Privacy Metrics" (arXiv:2312.03054) は、DCR / NNDR が MIA 成功率と単調関係にないことを実証している。DCR は **低頻度レコードを過剰保護**し、**頻出レコードの攻撃リスクを過小評価**する。スケール依存性（連続 vs 離散）もある。
2. **属性推論ベースラインの欠落**（Priv 指摘 3）: 合成データ評価の事実上の標準である **Generalized CAP (Correct Attribution Probability)** / **TCAP** が spec に無い。DCR より CAP の方が「実個票と属性が一致する確率」を直接推定でき、頻出レコード攻撃にロバスト。
3. **shadow model 前提の MIA を単体併置**（Priv 指摘 3）: TAPAS の MIA は shadow generator を前提とするが、spec は「shadow model なしで TAPAS を使う」と誤読できる記述だった。

加えて、評価用の実個票の出所・倫理処理が旧版 spec には無かった（Priv 指摘 2 末尾、Priv S5/S6）。これは ADR-0003 のスコープ外だが、本 ADR と同時に `docs/assumptions.md` で取り扱う。

## Decision

秘匿性評価を性質の異なる **3 層** に分ける。`evaluate/privacy_metrics.py` の I/F もこの層に合わせる。

### (a) 類似度 proxy（MVP、Phase 4）

- **DCR** (Distance to Closest Record)
- **NNDR** (Nearest Neighbor Distance Ratio)
- **ARD** (Harada 2024 由来の平均レコード距離指標)
- 距離は **Gower** を primary（連続は [0,1] 正規化、カテゴリはマッチ/非マッチ）
- **本層は proxy に過ぎない旨を `report.md` に自動注記**し、単体で privacy claim を張らない

### (b) 属性推論 baseline（**MVP 必須**、Phase 3.5 先行 → Phase 4 本実装）

- **Generalized CAP** (Taub et al. 2018 ほか)
- **TCAP** (Targeted CAP)
- Per-family_type 分解も出力
- **DCR/NNDR/ARD よりも先に実装する**（実装順序: rare_cell → CAP → DCR/NNDR/ARD → MIA）

### (c) shadow-based MIA（Phase 5 stretch）

- **TAPAS** (Houssiau et al. 2022)
- **DOMIAS** (van Breugel et al. 2023)
- **shadow generator を同一統計入力の異なる seed 群で再生成**する protocol を `docs/experiment_plan.md` に pre-register
- 本層は stretch goal とし、欠けていても v0.2 は出荷できる

### 将来の差分プライバシー (DP) 拡張への備え

- `domain/protocols.py` に `Distribution` / `PrivacyMetric` Protocol を**空定義で先置き**する
- `optimize/objective.py` は `target` を `Distribution` 型で受け取り、`.sample()` / `.mean()` を持つ抽象化に寄せる
- これにより DP-ε 計算器を後付けしても spec が壊れない（Priv S7）

### Rare cell 監視

- `family_type × age` で cell size < 5 の割合、unique 率を `evaluate/rare_cell_metrics.py` で監視
- §11.6 の soft constraint（rare cell 比率が閾値超過で trial を rejected とする）と連動

## Consequences

### 肯定的な結果

- **研究としての正当性**: proxy / baseline / MIA の 3 層結果を併記することで、単一指標に依存しない主張が可能
- **実装順序が合理的**: CAP を先に実装することで、Phase 3b の実験 1/2 段階でも属性推論リスクを測れる
- **文献整合**: Ganev & De Cristofaro (2024) の指摘に spec 上で応答している
- **将来拡張の余地**: DP・TAPAS/DOMIAS を後付けできる

### 否定的な結果

- **実装コストが増える**: CAP は Phase 3.5 で先出ししつつ、shadow seed 運用も Phase 5 で設計する必要がある
- **評価用実個票が必要**: 3 層すべてが「real individual-level records」を前提とするため、`docs/assumptions.md` の semi-synthetic protocol（ACS PUMS / IPUMS 等）が成立しないと評価できない
- **report 読者の負担増**: 3 層の値を読むガイドを `docs/spec/metrics.md` と `report.md` 冒頭に必ず置く

### 評価実行のゲート

- Phase 3.5 の Exit 条件: `synthpop-jp evaluate` が rare cell + CAP を出力できること
- Phase 4 の Exit 条件: proxy 層と CAP が両方出ること
- Phase 5 は stretch、出なくても v1.0 は出せる

## References

- レビュー指摘の逆参照:
  - `docs/reviews/review-privacy.md` 指摘 2（類似度 proxy の既知バイアス）
  - `docs/reviews/review-privacy.md` 指摘 3（CAP 欠落、shadow 前提の誤解）
  - `docs/reviews/review-privacy.md` 指摘 4（rare cell と秘匿性の緊張）
  - `docs/reviews/review-privacy.md` S7（DP 拡張への備え）
- `docs/reviews/action-plan.md` §2A「§13.3 の 3 層再構成」
- `docs/spec/spec.md` §13.3、§11.6
- 参考文献:
  - Ganev & De Cristofaro (2024) "On the Inadequacy of Similarity-based Privacy Metrics" arXiv:2312.03054
  - Houssiau et al. (2022) "TAPAS"
  - van Breugel et al. (2023) "DOMIAS" ICML
  - Taub et al. (2018) "Differential Correct Attribution Probability"
  - Platzer & Reutterer (2021) "Holdout-Based Empirical Assessment" Front. Big Data
  - Stadler et al. (2022) "Synthetic Data – Anonymisation Groundhog Day" USENIX Security
  - Harada et al. (2024) `docs/papers/harada_2024.pdf`
- 関連 ADR: ADR-0001（内部表現）、ADR-0002（目的関数）
