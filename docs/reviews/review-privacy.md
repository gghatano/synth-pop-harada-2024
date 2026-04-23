# プライバシー研究者視点レビュー

## サマリ（3〜5行）

Murata 2017 の SA ベース SR 手法の再現としては §5, §10〜§12 の骨格は妥当だが、(a) 目的関数の式形（重み付き絶対誤差の「重み」の扱い）と §11.4 の記法が原論文の式(1)(2)(3) と乖離しており忠実度に疑義がある、(b) §13.3 の秘匿性評価が「近傍距離中心」であり、合成データ文献で繰り返し指摘されている DCR の既知バイアス（低頻度レコード過剰保護・非等方性・スケール依存）への対処が欠けている、(c) §14.3 の rule-based tuner が「有用性 ↑ かつ DCR ↓ なら iteration 調整」と単純化しており、有用性・秘匿性・統計整合性の多目的性が明示化されていない、の 3 点が研究の妥当性に直結する重大な弱点である。実験設計 §15 も乱数ばらつき・多重検定・ベースラインが未指定で、再現実験としての主張強度を下げる。

## 重大な指摘（研究としての妥当性に関わる）

### 【指摘1】§11.4 の目的関数式が原論文の式(1)(3) と不整合

- **現状**: §11.4 は `objective = sum_s sum_j weight_s * abs(observed[s,j] - target[s,j])` と書いている。
- **問題**: 原論文 式(1) は `f(A) = Σ_s Σ_j |c_{sj}(A) - Round(r_{sj} · m_{sj}(A))|`、拡張版 式(3) は `f'(A) = Σ_s Σ_j |c_{sj}(A) - R_{sj}|`（`R_{sj}` は実数値の実統計）であり、**重み `weight_s` は原論文には存在しない**。また原論文では「9 統計版は rate × 分母のラウンド、21 統計版は実数値そのもの」という区別がある。spec はこれを区別せず、かつ `weight_s` を入れてしまっており、§18 の `weights: father_child_gap: 1.0 ...` と合わせると「再現実験」と「重み付きチューニング」が同居して、Murata 2017 の再現性主張が薄まる。
- **提案**:
  - §11.4 を「原論文準拠モード（weight 無し）」と「研究拡張モード（weight 有り）」に分離する。実験 1（§15.1）は前者のみで実施し、統計整合性評価も原論文 Table 13 の 21 統計別誤差を対応付けて報告する。
  - `Round(r_{sj} · m_{sj}(A))` が「生成集団側の分母に依存する動的ターゲット」である点を §11.4 で明記する。これを書かないと実装で target を静的定数として扱う誤実装を誘発する。
- **参考文献**: Murata, Harada, Masui (2017) 式(1), (3), および §4。

### 【指摘2】DCR/NNDR 中心の秘匿性評価は既知バイアスにさらされており「proxy」表記を越えた主張をしない明文化が必要

- **現状**: §13.3 初期実装で「最近傍距離 (DCR)」「NNDR」「レコード一致率」「属性部分一致率」「ARD」を列挙し、TAPAS/MIA/AIA を「拡張候補」に置いている。
- **問題**:
  1. DCR は **低頻度レコードを過剰保護（外れ値は常に遠い）**し、**頻出レコードの攻撃リスクを過小評価**する。Ganev & De Cristofaro (2024) "On the Inadequacy of Similarity-based Privacy Metrics" は、DCR/NNDR が MIA 成功率と単調関係にないことを実証している。
  2. 距離のスケール依存（連続変数 vs 離散変数、年齢 0〜100 と sex {0,1} の混在）で metric が支配的変数に引っ張られる。§13.3 は距離定義を明示していない。
  3. Murata 2017 はサンプルなしで生成するため、そもそも「実個票との最近傍距離」を計算する対象（実 individual-level records）が研究室にあるのか、§7.1 の入力仕様（集計表のみ）と矛盾する。**DCR を評価するためには評価用の実個票が別途必要**で、その出所・倫理承認が §7 に書かれていない。
- **提案**:
  - §13.3 冒頭に「本実装の DCR/NNDR/ARD は類似度 proxy に過ぎず、単体で privacy claim の根拠にしない」と明記。
  - 距離定義（Gower 距離を推奨、連続は [0,1] 正規化、カテゴリはマッチ/非マッチ）を §13.3 に追加。
  - 評価用 "real" 個票の出所を §7 に追加（e-Stat 個票は通常取得できないため、**合成データ研究で標準的な semi-synthetic 設定**: 実個票データセット（例: ACS PUMS サブセット、国勢調査公開ミクロデータ、IPUMS）から集計を作って合成し、元個票を hold-out として DCR 評価する、という設定を明示）。
  - MIA/AIA を「拡張候補」ではなく **Phase 4 必須 MVP** に昇格（後述）。
- **参考文献**: Ganev & De Cristofaro (2024) arXiv:2312.03054; Platzer & Reutterer (2021) "Holdout-Based Empirical Assessment" Front. Big Data; Stadler et al. (2022) "Synthetic Data – Anonymisation Groundhog Day" USENIX Security.

### 【指摘3】Shadow model 無しでの MIA 評価は MVP 段階でも不適切、そして CAP/AIA baseline が欠落

- **現状**: §13.3 「拡張候補」に「TAPAS による MIA」「TAPAS による AIA」「shadow modelling」を並列列挙。
- **問題**: TAPAS (Houssiau et al. 2022) の MIA は shadow generator を前提に設計されており、「shadow model なしで TAPAS を使う」記述は誤解を招く。また、**属性推論評価では Generalized CAP (Correct Attribution Probability)** が SDV/Synthetic Data Vault 評価の事実上の標準であり、これが spec に無い。DCR より CAP のほうが「実個票と属性が一致しうる確率」を直接推定でき、頻出レコード攻撃にロバスト。
- **提案**:
  - §13.3 を 3 層に再構成: (a) 類似度 proxy (DCR/NNDR/ARD), (b) **属性推論 baseline (Generalized CAP, TCAP)**, (c) **shadow-based MIA (TAPAS, DOMIAS)** を明示区分。
  - (b) を MVP 必須、(c) を Phase 4 の stretch goal。
  - shadow model を回すには同じ統計入力を異なる seed で再生成する protocol が必要で、§15 の実験設計に「shadow seed 群」を組み込む。
- **参考文献**: Houssiau et al. (2022) "TAPAS"; Taub et al. (2018) "Differential Correct Attribution Probability"; van Breugel et al. (2023) "DOMIAS" ICML.

### 【指摘4】目的関数最小化と秘匿性の緊張関係が spec で不可視化されている

- **現状**: §14.3 に「有用性が高いが近傍距離が小さすぎる → penalty または iteration 制限を調整」の 1 行のみ。
- **問題**: Murata 2017 はサンプル無しだが、拡張 21 統計に含まれる **family type 別人口ピラミッド（§5, 21 統計の J〜W）** を強く最小化すると、低頻度 family type（例: "couple and a parent" 1.48%, "couple and parents" 0.47%）に対し、ほぼ **集計表から一意に決まる年齢構成** が生成され、実個票がある場合は属性推論耐性が劇的に下がる。spec はこの「rare cell の overfitting 問題」を §11 でも §13 でも議論していない。
- **提案**:
  - §11 または新節 §11.6 として「目的関数最小化の下限と秘匿性」を追加。**rare family type × age cell の k-anonymity 下限**（合成集団上での cell size ≥ k）を soft constraint として導入、または目的関数に `-λ · H(生成分布)` のエントロピー正則化を加える選択肢を提示。
  - §13.3 に「family_type × age の rare cell 分布」メトリクスを追加（生成側で cell < 5 の割合をレポート）。
  - §15 の実験に「evals_per_agent を増やすと error ↓ だが rare cell unique 率 ↑」のトレードオフ曲線を主張指標として追加。
- **参考文献**: Elliot et al. (2018) "Functional Anonymisation"; Hittmeir et al. (2020) "A baseline for attribute disclosure risk"; SDV utility/privacy tradeoff 文献。

## 中程度の指摘（評価器実装時に対応すべき）

### 【指摘5】統計整合性 (§13.1) の距離指標の曖昧さ

- **現状**: §13.1 は「総目的関数値/統計別誤差/平均絶対誤差/相対誤差/人口ピラミッド差分/family type 別人数差分」を列挙するのみで、L1/L2/TV/JS/Hellinger の使い分けが書かれていない。§13.2 broad utility は「JS 距離または TV 距離」と or 表記。
- **提案**:
  - §13.1 は L1 (= 原論文式(1) の絶対誤差) をプライマリ、L2 と χ² をセカンダリに固定。
  - §13.2 の broad utility は **TV をプライマリ（L1/2 と等価で解釈容易）**, JS を参考指標に固定。「or」表記を排除。
  - 人口ピラミッドは age 1 歳刻みで年齢別 TV、5 歳刻みの集約 TV、の両方を報告（原論文が 5 歳刻みを使う箇所と 1 歳刻みを使う箇所が混在するため）。

### 【指摘6】Broad utility の「全属性ペア相関差」が未定義

- **現状**: §13.2 「相関差」とだけ記述。
- **問題**: カテゴリ変数（family_type, role, sex）× 連続変数（age）の混在で Pearson は不適切。Theil's U / Cramér's V / Correlation Ratio の使い分けが要る。
- **提案**: `dython.associations` 準拠の混合型相関行列を明示、差分は Frobenius norm / max-abs の両方を出す。

### 【指摘7】Narrow utility のダウンストリームタスク選定方針が不在

- **現状**: §13.2 "ダミー目的変数を用意し" とのみ。
- **問題**: タスクが任意だと結論が cherry-pick できる。Murata 2017 の主眼は household composition 再現なので、タスクも household 起点にする。
- **提案**:
  - 固定タスク A: "family_type 分類" (age, sex, 世帯内 role 分布 → family_type)
  - 固定タスク B: "世帯人数回帰" (family_type, 子ども人数 → household_size)
  - 固定タスク C: "役割予測" (age, sex, family_type → role)
  - 評価は TSTR (Train Synthetic Test Real) と TRTS を両方、分類は macro-F1、回帰は RMSE を事前登録。

### 【指摘8】乱数ばらつきの統計検定 (§15) 未設定

- **現状**: 原論文 Table 11〜13 は "averaged over ten trials" で平均と SD を出すに留まる。§15 は「同一 seed 群」と書くのみで trial 数・検定手法が未定。
- **提案**:
  - 各条件 n=10〜30 seed, 主要指標は Welch's t または Mann–Whitney U、多重比較は Holm 補正。
  - §15.1 の 1000 / 16000 evals 比較は Wilcoxon signed-rank（seed 対応あり）で effect size (Cliff's δ) も報告。
  - 報告指標・仮説を実験開始前に `docs/experiment_plan.md` に pre-register（§20 に既に記載ありだが §15 から明示参照する）。

### 【指摘9】改善ループの多目的最適化としての定式化不足 (§14)

- **現状**: §14.3 は if-then rule 4 本。§14.4 で multi-objective optimization を「将来」と位置付け。
- **問題**: 本研究の本質は「統計整合性 × 有用性 × 秘匿性」の 3 目的最適化であり、**Pareto フロント可視化は MVP 級の成果物**。rule-based tuner は単目的スカラー化しており、研究貢献として薄い。
- **提案**:
  - §14.3 に加えて「Pareto-based trial selection」を Phase 5 MVP に格上げ：全 trial を 3 次元スコア空間にプロットし non-dominated set を抽出。
  - rule_based は baseline 扱いとし、`--strategy {rule_based, pareto, random_search}` で切替可能に。
  - §18 config の `improve.strategy` 選択肢を列挙。

## 軽微な指摘・将来拡張の備え

- **(S1) §8 データモデル**: `kinship_id` が `Optional[str]` だが、原論文 §2 は kinship を「parent-child/husband-wife の関係検出用 ID」と定義している。kinship **graph** として表現できる型（`List[Tuple[person_id, person_id, relation]]`）の方が age_diff 評価で使いやすい。
- **(S2) §10.1 step 6**: "粗い人口ピラミッドまたは family type × role × sex 分布" と or 表記だが、原論文 §3 は「初期生成で 21 統計のうち F〜W を誤差 0 にする」手続き。**この誤差ゼロ初期化が原論文の肝**なので、§10 に明示。
- **(S3) §12.3 停止条件**: 原論文は `evals_per_agent ∈ {1000, 2000, 4000, 8000, 16000}` で Fig.5 を描いている。spec はこの具体値を持たず、`target_threshold` と `patience` を追加している。原論文再現のため §15.1 の比較は 5 水準を固定値として §18 に書く。
- **(S4) §13.3 ARD**: ARD (Average Record Distance?) の定義が spec 内に無い。DCR との区別を明記。
- **(S5) §7.1 入力**: e-Stat など公的統計の利用時は **出典表記義務**（統計法 §44 および e-Stat 利用規約）があり、§17 CLI または §7.2 出力 `report.md` に自動で出典を埋めるフィールドが必要。
- **(S6) IRB/利用規約**: 実個票（PUMS/IPUMS）を DCR 評価に使う場合、大学 IRB と data use agreement が要る。§3 で「法的判定の自動化は非目的」としているが、**実験データ出所の倫理記録**（どのデータセット・どの版・誰が取得）は §20 の `docs/assumptions.md` の必須項目にすべき。
- **(S7) 将来の DP 拡張への備え**: §3 で DP は非目的だが、将来拡張で spec を壊さないために、
  - `optimize/objective.py` を「noisy target を受け取れる」I/F にする（`target` を `Distribution` 型にし、`.sample()` か `.mean()` を持つ抽象化）。
  - 評価器側も privacy metric を `PrivacyMetric` protocol で抽象化し、後で DP-ε 計算器を差し込めるようにする。
  specにこの抽象化要件を §9 または §21 に一行入れるだけで将来の破壊的変更を避けられる。

## 追加で必要と考えるタスク

- **タスクA: 評価用 real-data protocol の整備** — 成果物: `docs/assumptions.md` に semi-synthetic プロトコル（どの公開個票を hold-out に使うか、cell size 制限、利用規約）を記載。Phase 1 (MVP 着手前) に完了させる。
- **タスクB: Generalized CAP / TCAP 評価器の実装** — 成果物: `src/synthetic_population/evaluate/attribute_inference.py` と `tests/`。Phase 4 必須。
- **タスクC: Pareto フロント可視化** — 成果物: `src/synthetic_population/experiments/pareto.py`, `outputs/*/pareto.png`。Phase 5 必須。
- **タスクD: 原論文 Table 13 (21 統計別平均誤差) 再現** — 成果物: `docs/reports/phase-03-murata-replication.md` に同形式の表、論文値との差分を報告。Phase 3。
- **タスクE: 実験事前登録文書** — 成果物: `docs/experiment_plan.md` に仮説・指標・検定手法・サンプルサイズを実験着手前にコミット。Phase 3 着手前。
- **タスクF: rare cell 監視メトリクス** — 成果物: `evaluate/rare_cell_metrics.py`（family_type × age で cell<5 の割合、unique 率）。Phase 4。
- **タスクG: 距離定義の明文化と単体テスト** — 成果物: `domain/distance.py`（Gower 距離）と unit test。Phase 4 冒頭。
- **タスクH: 出典自動埋め込み** — 成果物: `io/writers.py` の `report.md` ジェネレータに出典セクション。Phase 4。

## 評価指標の優先順位（MVP→拡張）

- **MVP 必須（Phase 3 完了時点で出せる）**:
  - 原論文式(1)(3) 準拠の統計別 L1 誤差（21 統計ブレークダウン）
  - 総 error の seed 間平均±SD（原論文 Table 11,12 対応）
  - 計算時間（原論文と同形式）
  - family_type / sex / age の marginal TV 距離
- **Phase 4 で追加（評価器 MVP）**:
  - Broad utility: 全属性ペア TV, 混合型相関行列差の Frobenius norm
  - Narrow utility: TSTR/TRTS on 固定 3 タスク (A,B,C 指摘 7)
  - Privacy proxy: DCR/NNDR/ARD（Gower 距離、定義明記）＋ rare cell unique 率
  - **属性推論: Generalized CAP / TCAP**
- **Phase 5 以降の拡張候補**:
  - shadow-based MIA (TAPAS, DOMIAS)
  - holdout distinguishing test
  - Pareto-based improvement loop
  - 属性別プライバシー分解 (per-family_type CAP)

## Phase 順序への提案

1. **Phase 0（spec 改訂）を追加**: §11.4 の式訂正、§13.3 の 3 層再構成、§14.3 の多目的化を spec に反映してから実装着手。これをやらないと実装と spec が最初から乖離する。
2. **Phase 3 と Phase 4 の間に「評価器先出し Phase 3.5」を挟む**: Phase 3 で age-swap を実装する前に、評価器 (統計別誤差レポータ + Table 13 形式出力) を先に作る。そうしないと age-change/age-swap 比較の「正解」が持てない。原論文再現の成否判定は評価器に依存する。
3. **Phase 4 の privacy 評価は DCR より先に CAP を実装**: DCR は "proxy" に過ぎず、CAP の方が単独で論文貢献になる。実装順序を `rare_cell → CAP → DCR/NNDR/ARD → (Phase 5) MIA` とする。
4. **Phase 5 の rule-based tuner と Pareto 可視化を並列実装**: §14.3 の rule は baseline、§14.4 の multi-objective を前倒しし「rule vs Pareto の比較」を §15.3 の実験 3 の主対象にする。こちらの方が論文としての主張が立つ。
5. **実験事前登録（タスクE）を Phase 3 開始前にハードゲートにする**: §15 の実験設計が曖昧なまま実装に入ると、事後の指標選択バイアスが入る。`docs/experiment_plan.md` を git tag でフリーズしてから Phase 3 着手。
