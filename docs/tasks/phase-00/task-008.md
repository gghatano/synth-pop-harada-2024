# task-008: ADR 0001〜0004 の記述（設計決定の凍結）

## 目的

Phase 0 で確定した 4 つの構造的決定を Architecture Decision Record として永続化する。以降の議論で蒸し返されたとき、ここを根拠点として戻れる状態にする。

## 前提・依存

- action-plan.md §1 を一次情報源とする。
- task-003, task-004, task-007 の実装は ADR を前提に進む（ADR 先、実装後という順序）。

## 成果物

### a. `docs/adr/README.md`

ADR の書式規約（Michael Nygard テンプレ準拠: Status / Context / Decision / Consequences）、番号付け規約、Superseded 運用。

### b. `docs/adr/0001-internal-representation.md`

- **Status**: Accepted
- **Context**: §8 の `list[Person]` OOP 表現を SA 内ループで使うと N×max_iters で非現実的な速度になる（Py 指摘1）。
- **Decision**: I/O・外部 API は pydantic v2、SA 内部は `PopulationArrays`（NumPy 並列配列 int16/int8/int32）+ 差分更新で `observed[s,j]` を保持変数に反映する。`propose/apply/revert` の 3 メソッド API で遷移を閉じ込める。
- **Consequences**: +性能（1 遷移 O(1)）、+決定性テスト容易、−OOP 的記述は I/O 層に限定。差分更新と全再計算の一致を hypothesis で property test。

### c. `docs/adr/0002-objective-normalization.md`

- **Status**: Accepted
- **Context**: §11.4 の式が原論文式(1)(3) と乖離、かつ統計間セル数差を無視すると demographic pyramid が支配する（Py 指摘4 / Priv 指摘1）。
- **Decision**: 目的関数を 2 モード化:
  - 原論文準拠モード: `f(A) = Σ_s Σ_j |c_{sj}(A) - Round(r_{sj}·m_{sj}(A))|`、式(3) は `R_{sj}` 直接。`weight_s` 無し。実験 1 (§15.1) の Murata 再現はこちらのみ。
  - 研究拡張モード: `loss_s = (1/|cells_s|) Σ_j |rate_obs - rate_target|; objective = Σ_s weight_s * loss_s`。§18 の weights はこちらに適用。
- **Consequences**: Murata 再現の忠実度確保と実用的なチューニングを両立。評価レポートは両モードの値を併記する。

### d. `docs/adr/0003-privacy-evaluation-layers.md`

- **Status**: Accepted
- **Context**: §13.3 の DCR 中心の評価は Ganev & De Cristofaro (2024) などで proxy としての限界が示されている（Priv 指摘2,3）。
- **Decision**: 評価を 3 層に分離する:
  - (a) 類似度 proxy: DCR / NNDR / ARD（Gower 距離、proxy 注記必須）
  - (b) 属性推論 baseline: **Generalized CAP / TCAP（MVP 必須）** ← Phase 4 の中で DCR より先に実装
  - (c) shadow-based MIA: TAPAS / DOMIAS（Phase 5 stretch）
  - `Distribution` / `PrivacyMetric` Protocol を先置きし、将来の DP 拡張で spec を壊さない設計（Priv S7）。
- **Consequences**: 研究貢献として「proxy ↔ baseline ↔ MIA の層別結果」を報告可能。実装順序が spec 記載順と異なるので task-001 で spec §13.3 を書き換える。

### e. `docs/adr/0004-naming-and-license.md`

- **Status**: Accepted（ユーザー承認: 2026-04-23）
- **Context**: リポジトリ名 `synth-pop-harada-2024` / spec §9 パッケージ名 `synthetic_population` / PyPI 未定 の三重ズレ（OSS 指摘1,2）。
- **Decision**:
  - PyPI 名: `synthpop-jp`
  - import 名: `synthpop_jp`
  - CLI エントリ: `synthpop-jp`
  - LICENSE: Apache-2.0
  - sample_case は完全合成ダミー、e-Stat 実データは再配布しない
  - 引用は `CITATION.cff` に Murata 2017 + Harada 2024 を preferred-citation、Zenodo DOI は v0.1 公開時
- **Consequences**: PyPI 公開時の衝突回避、Murata+Harada 由来であることの検索性向上、研究ユーザー向けの特許条項保護。

## 受け入れ基準

- 上記 5 ファイルが `docs/adr/` に存在する。
- 各 ADR が Status / Context / Decision / Consequences の 4 セクションを持つ。
- ADR 0001〜0004 それぞれに「どのレビュー指摘を出典とするか」の逆参照リンクがある。
- 今後 ADR は Superseded フィールドで上書き管理（新規決定は 0005 以降）。

## 推定規模

S（2〜3 時間）。

## 参照

- `docs/reviews/action-plan.md` §1, §2B
- `docs/reviews/review-python.md` 指摘 1, 4, 追加タスクF
- `docs/reviews/review-privacy.md` 指摘 1〜4, S7
- `docs/reviews/review-oss.md` 指摘 1, 2
