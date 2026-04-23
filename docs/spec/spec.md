# Spec: Murata 2017 と「生成・評価・改善」型の合成人口データ実装

本ドキュメントは `synthpop-jp` プロジェクトの中核仕様書である。実装詳細の一部は `docs/spec/data_contract.md` / `docs/spec/metrics.md` / `docs/spec/experiment_report_format.md` / `docs/experiment_plan.md` / `docs/assumptions.md` / `docs/adr/` に委譲する。

## 1. 背景

本実装の目的は、公開統計（集計表）から世帯・個人レベルの合成人口データを生成する Murata et al. (2017) の simulated annealing (SA) ベース手法を、Python で再現可能な形で実装し、その上に「生成 → 評価 → 改善」の反復ループを載せることで、実験可能な研究用プロトタイプを構築することである。

Murata 2017 はサンプル個票を使わず、公開統計に整合する世帯構成・個人属性を SA で探索的に再構成する手法である。候補解遷移として `age-change` と `age-swap` を比較し、探索回数が少ないときは age-change が有利、十分な探索回数があるときは age-swap が有利であることを報告している。目的関数は統計表との差の総和であり、初期集団生成・候補解遷移・追加統計による評価の 3 点が改良点として示されている。

Harada et al. (2024)（仮想都市データに関する研究、`docs/papers/harada_2024.pdf`）は、合成人口データの**有用性と秘匿性をどのように評価するか**の基準を与える。とくに ARD（Average Record Distance 系の距離指標）のような評価軸は、本実装の `evaluate/privacy_metrics.py` の設計指針として取り込む。本実装は「生成手法は Murata 2017、評価軸は Harada 2024」を両輪として位置付ける。

合成人口は公開集計表から数値計算を繰り返して差を最小化する探索的生成が有力であり、単発生成ではなく、複数データセットを生成・評価しながら利用する前提が適している。本 Spec では、Murata 2017 の再現をコア実装とし、その外側に「生成・評価・改善」ループを設ける。

## 2. 目的

### 2.1 主目的

1. 公開統計を入力として、世帯・個人属性を持つ合成人口データを生成できること。
2. Murata 2017 の `age-change` / `age-swap` を切り替えて比較できること。
3. 生成結果を統計整合性・有用性・秘匿性の観点で評価できること。
4. 評価結果を用いて、次の生成条件を自動更新する改善ループを持つこと。
5. 小規模ダミーデータで end-to-end 実行できること。

### 2.2 副目的

* 都道府県統計や仮想都市データに差し替えやすい構成にする。
* 将来、shadow-based MIA（TAPAS / DOMIAS 等）による評価を追加できるようにする。
* 生成された複数候補を保存し、比較レポートを出せるようにする。

## 3. 非目的

以下は今回のスコープ外とする。

* 日本の実統計表を完全収集して全国再現すること
* 高速化の最適化（C++ 化、GPU 化、分散実行）
* GUI の実装
* 差分プライバシー (DP) 保証付き生成器の実装（ただし将来拡張に備えた Protocol 抽象は用意する）
* 画像・時系列・自由記述を含む非表形式データへの拡張
* 法的判定の自動化

## 4. 実装対象の考え方

本プロトタイプでは、Murata 2017 の「公開統計から世帯・個人属性を再構成する SR 手法」を最小実装し、その周囲に評価と改善の管理層を追加する。

### 4.1 コア生成器

* 世帯タイプ別の世帯数を生成
* 世帯人数・子ども人数を割当
* 各エージェントに性別・年齢・役割を割当
* SA により年齢構成を統計表へ近づける

### 4.2 評価器

* 統計整合性評価
* 有用性評価（broad / narrow）
* 秘匿性評価（類似度 proxy / 属性推論 baseline / shadow-based MIA の 3 層）
* 実験メタデータ保存

### 4.3 改善器

* 遷移方式変更（age-change / age-swap / 混合）
* 温度スケジュール変更
* 目的関数重み変更（研究拡張モードのみ）
* 初期解生成パラメータ変更
* 停止条件の延長・短縮

## 5. 参照手法の要点

### 5.1 Murata 2017 の実装要点

Murata 2017 は、9 種類の家族類型、子ども人数統計、人口ピラミッド、親子年齢差、夫婦年齢差などの公開統計を用い、SA により誤差を最小化する。元の 9 統計ベース目的関数 `f(A)` と、拡張後の 21 統計ベース目的関数 `f'(A)` が示されている。候補解遷移としては、

* `age-change`: 役割に応じた年齢分布に従い 1 人の年齢を変更
* `age-swap`: 同一 family type・同一 sex の 2 人の年齢を交換

の 2 方式がある。`age-swap` は family type 別人口構成を保ちやすい。

### 5.2 生成・評価・改善の考え方

本実装では「一度生成して終わり」ではなく、評価に基づく再生成を前提とする。1 回の SA では探しきれない局所解を、設定を変えた複数 trial の中から選ぶことを想定する。

### 5.3 評価観点

* 統計整合性
* 有用性（broad utility / narrow utility）
* 秘匿性（proxy / baseline / MIA の 3 層。§13.3 参照）

### 5.4 Murata 生成 / Harada 評価の役割分担

本実装は 2 つの先行研究を明確に**役割分担**して使う。

* **Murata 2017 は「生成側」の根拠**: SA ベースの SR 手法、21 統計への誤差最小化、age-change / age-swap 遷移の比較設計など、§10〜§12 の生成ロジックと §11 の目的関数はここに由来する。
* **Harada 2024 は「評価側」の根拠**: 有用性と秘匿性の評価軸、特に §13.3 (a) 層に置く ARD のような距離ベース指標はここに由来する。§13 の評価指標体系はこちらを参照する。

spec 本文中の各節には、由来する論文を脚注または「§13.3 (a) ARD (Harada 2024)」のように括弧書きで明示する。

## 6. システム要件

### 6.1 開発言語・環境

* **Python 3.11+**
* パッケージ管理: `uv`、lockfile (`uv.lock`) をコミットし CI は `uv sync --frozen` で再現する
* **PyPI パッケージ名: `synthpop-jp`**
* **import 名: `synthpop_jp`**
* **CLI エントリポイント: `synthpop-jp`**（`[project.scripts]` に登録）
* **ライセンス: Apache-2.0**（研究ユーザー向けの特許条項保護を重視、ADR-0004 参照）
* 実装形態: ライブラリ + CLI
* OS: Linux / macOS を想定

### 6.2 想定ライブラリ

* `numpy`（SA 内部表現の主、ADR-0001 参照）
* `pandas`（I/O 層のみで使用）
* `scipy`
* `pydantic` v2（I/O バリデーション、config ローダ）
* `pydantic-settings`
* `typer`
* `matplotlib`
* `pyyaml`
* `rich`（進捗・構造化ログの人間可読レンダリング、`tqdm` は使わない）
* `structlog`（機械可読ログ）
* `scikit-learn`

## 7. 入出力仕様

本節は概要のみを示す。**全 CSV の列・型・単位・欠損規則・半開区間表現・`family_type_group` との対応などの詳細は [`docs/spec/data_contract.md`](data_contract.md) に委譲する**。

### 7.1 入力（概要）

必須入力:

1. `family_type_counts.csv`（family type ごとの世帯数）
2. `children_count_dist.csv`（family type group 別、子ども人数分布）
3. `demographic_by_age_sex.csv`（年齢 × 性別の人口）
4. `age_diff_parent_child.csv`（親子年齢差の分布）
5. `age_diff_couple.csv`（夫婦年齢差の分布。符号規則 `couple_diff = husband_age - wife_age`）

任意入力:

6. `demographic_by_family_type_role.csv`（family type × role × sex × age）
7. `household_size_by_family_type.csv`
8. `config.yaml`（§18 参照）

各 CSV の列名・型・欠損規則・半開区間文字列 `"[-5,-3)"` の規約は `data_contract.md` に一元化する。

### 7.2 出力

1. `synthetic_households.csv`
2. `synthetic_persons.csv`
3. `metrics.json`（スキーマは `docs/spec/experiment_report_format.md`）
4. `report.md`（出典・ライセンス注記を自動埋込）
5. `artifacts/`
   * `artifacts/checkpoint/` — SA の再開用スナップショット（`--resume` で使用、10k 反復ごと）
   * `artifacts/trace/` — `trace.jsonl`（SA の反復ログ）
   * `artifacts/figures/` — 人口ピラミッドなどの PNG

## 8. データモデル

I/O 層の外部データモデル（pydantic v2）:

```text
Household
- household_id: str
- family_type: str
- household_size: int
- members: list[Person]

Person
- person_id: str
- household_id: str
- sex: Literal["M", "F"]
- age: int
- role: str
- kinship_id: Optional[str]
```

SA 内部表現は `PopulationArrays`（NumPy 並列配列、ADR-0001 参照）で、§9・§12 で詳述する。I/O とドメイン層は pydantic、SA 内部は並列配列、という二層構造を取る。

### 8.1 family_type の初期定義

* single
* couple
* couple_and_children
* father_and_children
* mother_and_children
* couple_and_parents
* couple_and_a_parent
* couple_children_and_parents
* couple_children_and_a_parent

### 8.2 role の例

* husband
* wife
* father
* mother
* child
* parent
* single

## 9. アーキテクチャ

`synthpop_jp` パッケージのディレクトリ構成を以下に固定する（命名の根拠は ADR-0004 を参照）。

```text
src/
  synthpop_jp/
    __init__.py
    cli.py                    # typer アプリ。[project.scripts] の synthpop-jp が参照
    config.py                 # pydantic-settings ベースの設定ローダ
    registry.py               # family_type / transition / evaluator のレジストリ
    domain/
      household.py
      person.py
      statistics.py
      protocols.py            # Transition / CoolingSchedule / Evaluator / PrivacyMetric / Distribution Protocol
      distance.py             # Gower 距離など
    io/
      loaders.py              # pydantic v2 ベースの CSV ローダ
      writers.py              # 出典・ライセンス注記を埋め込む report.md ジェネレータ
    init/
      household_sampler.py
      initial_population.py
    optimize/
      state.py                # PopulationArrays（NumPy 並列配列）
      objective.py            # 差分更新版 ObjectiveState（propose/apply/revert）
      annealing.py
      transitions.py
      cooling.py
    evaluate/
      aggregate_metrics.py    # 統計整合性
      utility_metrics.py      # broad / narrow utility
      privacy_metrics.py      # 3 層評価（proxy / CAP baseline / MIA skeleton）
      attribute_inference.py  # Generalized CAP / TCAP
      rare_cell_metrics.py    # family_type × age の cell size 監視
      downstream_tasks.py
    improve/
      tuner.py
      strategy.py             # rule_based / pareto / random_search
    experiments/
      runner.py
      comparison.py
      pareto.py
```

### 9.1 拡張ポイント（plugin）

外部パッケージから評価器・遷移・family_type を注入できるよう、次の 2 層で拡張点を提供する（OSS 指摘 5）。

* **内側（同一プロセス）**: `domain/protocols.py` の `Protocol`（`Transition`, `CoolingSchedule`, `Evaluator`, `PrivacyMetric`, `Distribution`）を実装し、`registry.py` の `register_family_type(name, template)` / `register_transition(name, fn)` / `register_evaluator(name, cls)` で登録する。
* **外側（別パッケージ）**: `pyproject.toml` の `[project.entry-points]` で登録する。名前空間は以下を使う。
  * `synthpop_jp.evaluators`
  * `synthpop_jp.transitions`
  * `synthpop_jp.family_types`

CONTRIBUTING.md に「新 family_type を足す 10 行の例」「新評価器を足す 20 行の例」を載せる。

## 10. 生成ロジック仕様

### 10.1 初期集団生成

1. family type 別に世帯数を生成
2. 各 family type に household size を割当
3. children を持つ family type に子ども人数を割当
4. role を household template から展開
5. sex を role に応じて設定
6. age を family type × role × sex 分布から割当（原論文 §3 は 21 統計のうち F〜W を初期生成で誤差 0 化する手続きを提示しており、Phase 3a でこの「初期誤差 0 化」を実装する。粗い人口ピラミッドのみを使う簡易モードは Phase 1〜2 の MVP 用に残す）

### 10.2 初期集団生成の方針

* 再現性のため乱数 seed を固定可能にする
* 乱数源は `numpy.random.Generator` のみを使い、`random` / `scipy.stats.random_state` は使わない
* `SeedSequence` による階層 spawning を §18 に明記（`init_rng`, `sa_rng`, `eval_rng`, trial 別 seed）
* 制約違反がある場合は household 単位で再生成する
* まずは小規模データで矛盾なく生成できることを優先する

## 11. 目的関数仕様

### 11.1 基本方針

目的関数は「公開統計と生成結果の差の総和」を基本とする。**本実装は 2 モードを併記する**（ADR-0002）。

* **原論文準拠モード**: Murata 2017 の式(1) / 式(3) に忠実。`weight_s` は使わない。Murata 再現を主張する場面ではこちらのみ。
* **研究拡張モード**: セル数正規化 + 統計間重み。実用チューニング向け。

実験 1（§15.1）は**原論文準拠モードのみ**で実施する。両モードの値は評価レポートで併記する。

### 11.2 第一段階: minimal objective

* father-child 年齢差誤差
* mother-child 年齢差誤差
* couple 年齢差誤差
* male demographic pyramid 誤差
* female demographic pyramid 誤差

### 11.3 第二段階: extended objective

family type 別 demographic pyramid まで拡張し、Murata 2017 の 21 統計に対応させる。

### 11.4 式（原論文準拠モード / 研究拡張モード）

#### 11.4.1 原論文準拠モード（primary）

Murata 2017 式(1)（9 統計ベース）:

```text
f(A) = Σ_s Σ_j | c_{sj}(A) - Round( r_{sj} · m_{sj}(A) ) |
```

* `A`: 現在の合成集団
* `s`: 統計のインデックス（family type 別や demographic 等）
* `j`: その統計内のセル（age bin, diff bin, family type 等）
* `c_{sj}(A)`: 合成集団から観測したセル `j` の個数
* `r_{sj}`: 公開統計が示す**率**（例: family type 別の age 分布）
* `m_{sj}(A)`: 合成集団側の**対応する分母**（例: その family type の人数）
* `Round(r_{sj} · m_{sj}(A))`: 率 × 分母を丸めた**動的ターゲット**

「`Round(r_{sj} · m_{sj}(A))` は生成集団側の分母に依存する動的ターゲットである」点を明記する。target を静的定数として扱うと誤実装になる。

Murata 2017 式(3)（21 統計ベース、実数値 `R_{sj}` を直接使う拡張版）:

```text
f'(A) = Σ_s Σ_j | c_{sj}(A) - R_{sj} |
```

* `R_{sj}`: 実数値の実統計（率ではなく集計人数）
* `weight_s` は存在しない

#### 11.4.2 研究拡張モード

セル数正規化 + 統計間重み（本実装独自、原論文の拡張）:

```text
loss_s    = (1 / |cells_s|) * Σ_j | observed_rate[s, j] - target_rate[s, j] |
objective = Σ_s weight_s * loss_s
```

* `observed_rate`: 合成集団のセル個数を人口総数で割った rate
* `target_rate`: 公開統計側の rate
* `weight_s`: §18 の `objective.weights` と対応。値域は **統計間の相対重要度** として解釈する
* このモードは Phase 3 以降のチューニング実験でのみ使う

### 11.5 ハード制約

**目的関数への加算ペナルティではなく、遷移前に弾くハード制約**として §12.2 に移す（Py 指摘 14）。以下は SA の提案段階でリジェクトする。

* 年齢が 0〜100 を外れる提案
* role と年齢が矛盾する提案
* 親が子より若くなる提案
* 夫婦の片方が未成年になる提案

ペナルティを目的関数に入れると温度チューニングに干渉するため、上記はハード制約として閉じ込める。

### 11.6 目的関数最小化と秘匿性

Murata 2017 の拡張 21 統計（family type 別人口ピラミッド）を強く最小化すると、低頻度 family type（例: "couple_and_a_parent" 1.48%, "couple_and_parents" 0.47%）の**集計から一意に決まる年齢構成**が生成され、評価用実個票がある場合は属性推論耐性が低下する（Priv 指摘 4）。

本実装は次の対策を仕様として用意する。

* **rare family_type × age cell の k-anonymity 下限**: 合成集団上で `family_type × age` の cell size が閾値 `k`（既定 5）を下回る割合をモニタし、`docs/spec/metrics.md` で定義する `rare_cell_metrics` に含める。`improve` でこの割合が閾値を超えた場合は trial を rejected としてマークする soft constraint オプションを設ける。
* **エントロピー正則化オプション**: 目的関数に `-λ · H(生成分布)` を加算する研究拡張モード限定のオプション（`objective.entropy_regularization` / `objective.lambda`）。既定は off。

§15 の実験では「evals_per_agent を増やすと error ↓ だが rare cell unique 率 ↑」のトレードオフ曲線を主張指標に含める。

## 12. SA 仕様

### 12.1 共通

* 初期温度 `T0`
* 冷却率 `alpha`
* 反復数 `max_iters`
* 評価回数 / person 上限 `evals_per_agent`
* 受理判定: Metropolis
* **内部表現は NumPy 並列配列 (`PopulationArrays`)、目的関数は差分更新前提**（ADR-0001）。1 遷移ごとに影響ビン（age_bin, sex, family_type 等）のみ `+1 / -1` し、`abs` の総和を保持変数 `score` に差分反映する。`ObjectiveState` クラスが `propose / apply / revert` の 3 メソッド API で全遷移を扱う。
* `--resume` のための checkpoint を 10k 反復ごとに `artifacts/checkpoint/*.parquet` に保存する

### 12.2 遷移方式

#### A. age-change

* family type を選択
* member を選択
* 役割に応じた分布から新年齢をサンプル
* §11.5 ハード制約を通過した提案のみを SA の Metropolis に渡す
* 受理時は `ObjectiveState.apply`、却下時は `revert`

#### B. age-swap

* family type と sex を選択
* 対応する 2 人を選択
* 年齢を交換
* §11.5 ハード制約を通過した提案のみを SA の Metropolis に渡す

#### C. hybrid

* `p_change` と `p_swap` で混合
* 初期探索では `age-change` を厚め、後半は `age-swap` を厚めにする設定を可能にする

### 12.3 停止条件

* `iter >= max_iters`
* `evals_per_agent >= limit`
* `best_score <= target_threshold`
* `patience` 期間改善なし

Murata 2017 Fig.5 の再現用に `evals_per_agent ∈ {1000, 2000, 4000, 8000, 16000}` の 5 水準を §18 の比較 config に置く。

## 13. 評価仕様

各指標の**距離定義・算出式の詳細は [`docs/spec/metrics.md`](metrics.md) に委譲する**。本節は方針と層構造のみを固定する。

### 13.1 統計整合性評価

* **L1 (= 原論文式(1) の絶対誤差) を primary**、L2 / χ² を secondary、TV を参考指標とする（Priv 指摘 5）
* 指標一覧:
  * 総目的関数値（原論文モード / 研究拡張モードの両方）
  * 統計別誤差（21 統計ブレークダウン、Table 13 形式）
  * 平均絶対誤差 / 相対誤差
  * 人口ピラミッド差分は **1 歳刻みと 5 歳刻みの両方を報告**
  * family type 別人数差分

### 13.2 有用性評価

#### Broad utility

* 単変量分布差（L1 / TV）
* クロス集計差（全属性ペア TV、Frobenius norm / max-abs）
* 混合型相関行列（`dython.associations` 準拠: Theil's U / Cramér's V / Correlation Ratio）
* プライマリ指標は **TV**、参考として JS 距離

#### Narrow utility

**固定 3 タスク**（Priv 指摘 7）を事前登録する。

* タスク A: family_type 分類（age, sex, 世帯内 role 分布 → family_type、macro-F1）
* タスク B: 世帯人数回帰（family_type, 子ども人数 → household_size、RMSE）
* タスク C: 役割予測（age, sex, family_type → role、macro-F1）

評価は TSTR（Train Synthetic, Test Real）と TRTS の両方を出す。タスク・指標・データ分割は `docs/experiment_plan.md` に事前登録して凍結する。

### 13.3 秘匿性評価（3 層）

秘匿性は性質の異なる 3 層に分けて報告する。Ganev & De Cristofaro (2024) "On the Inadequacy of Similarity-based Privacy Metrics" (arXiv:2312.03054) が示すとおり、類似度ベース指標単体では privacy claim の根拠として不十分である（Priv 指摘 2, 3）。

評価用 "real" 個票の出所・倫理処理は [`docs/assumptions.md`](../assumptions.md) を参照。距離定義（Gower 距離など）の具体は [`docs/spec/metrics.md`](metrics.md) に委譲する。

#### (a) 類似度 proxy（MVP、Phase 4）

* **DCR** (Distance to Closest Record)
* **NNDR** (Nearest Neighbor Distance Ratio)
* **ARD** (Harada 2024 由来の距離指標、`evaluate/privacy_metrics.py` のコアに置く)
* 距離は **Gower** を primary とし、連続は [0,1] 正規化、カテゴリはマッチ/非マッチ
* **本層は proxy に過ぎない旨を `report.md` に明記**し、単体で privacy claim を張らない

#### (b) 属性推論 baseline（MVP 必須、Phase 4 / Phase 3.5 先行）

* **Generalized CAP** (Correct Attribution Probability、Taub et al. 2018 ほか)
* **TCAP**
* DCR/NNDR/ARD より先に実装する（実装順序: rare_cell → CAP → DCR/NNDR/ARD → MIA）
* 属性別分解（per-family_type CAP）も出力

#### (c) shadow-based MIA（Phase 5 stretch）

* **TAPAS** (Houssiau et al. 2022)
* **DOMIAS** (van Breugel et al. 2023)
* shadow generator を同じ統計入力の異なる seed 群で再生成する protocol を `docs/experiment_plan.md` に事前登録

### 13.4 Rare cell 監視

* `family_type × age` で cell size < 5 の割合
* unique 率（1 人しかいない cell の割合）
* §11.6 と連動

## 14. 生成・評価・改善ループ

### 14.1 ループ概要

```text
for trial in trials:
    generate initial population
    optimize with SA
    evaluate utility / privacy / statistical fit
    record metrics
    update parameters (strategy に応じて)
select best configuration
```

### 14.2 改善対象

* transition type
* cooling schedule
* objective weights（研究拡張モードのみ）
* max iterations
* household initialization heuristics

### 14.3 改善戦略（baseline）: rule_based

if-then ルールを baseline として維持する。

* 親子年齢差誤差が大きい → `age-change` 比率を上げる
* demographic 誤差が小さいが親族関係誤差が大きい → `age-swap` を増やす
* rare cell unique 率が高い → `evals_per_agent` を下げる
* 収束が遅い → 温度減衰を緩める

### 14.4 改善戦略（MVP）: pareto / random_search

本研究の本質は「統計整合性 × 有用性 × 秘匿性」の 3 目的最適化である（Priv 指摘 9）。`improve.strategy` は以下 3 値を取る。

* `rule_based`（baseline、§14.3）
* `pareto`（MVP、全 trial を 3 次元スコア空間にプロットし non-dominated set を抽出、`outputs/*/pareto.png` を出力）
* `random_search`（参照用）

rule_based vs pareto の比較は §15.3 実験 3 の主対象とする。

将来拡張（Phase 6 以降）:

* Bayesian optimization
* bandit による遷移選択

## 15. 実験計画

**§15 の実験は事前登録必須**（Priv 指摘 8）。仮説・指標・統計検定・サンプルサイズ・停止条件は [`docs/experiment_plan.md`](../experiment_plan.md) に記載し、**Phase 3 着手前に git tag でフリーズ**する。報告指標の後付け変更は ADR を追加して追記管理する。

### 15.1 実験 1: Murata 再現の最小比較

* `age-change` と `age-swap` の傾向差を確認する
* **原論文準拠モード（§11.4.1）のみ**で実施する
* 同一 seed 群（n = 10〜30）
* 同一入力統計
* `evals_per_agent ∈ {1000, 2000, 4000, 8000, 16000}` の 5 水準
* 統計検定: **Wilcoxon signed-rank**（seed 対応あり）、effect size は **Cliff's δ**

### 15.2 実験 2: hybrid 戦略

* 初期 `age-change`、後半 `age-swap` の混合が有効か確認する
* Welch's t + Holm 補正

### 15.3 実験 3: 改善戦略の比較（rule_based vs pareto）

* 固定設定より改善ループのほうが総合評価が良いか確認する
* rule_based / pareto / random_search の 3 戦略を直接比較
* Welch's t + Holm 補正

### 15.4 実験 4: 複数候補のばらつき

* 単一合成人口ではなく複数データセット生成時のばらつきを確認する
* shadow seed 群の運用は `docs/experiment_plan.md` に定義

### 15.5 統計検定の既定

* seed 群: n = 10〜30
* 主指標: Welch's t（独立群）or Wilcoxon signed-rank（対応群）、多重比較は Holm 補正
* 信頼区間: bootstrap CI（2,000 回、percentile 法）
* `metrics.json` に `seed`, `git_sha`, `numpy_version`, `uv.lock hash` を必ず記録

## 16. 実装フェーズ

### Phase 0: 基盤整備（新設）

* spec.md 改訂、ADR 0001〜0004、命名・LICENSE 確定
* 契約ドキュメント骨子（data_contract / metrics / experiment_report_format / experiment_plan / assumptions）
* pyproject.toml / uv.lock / ruff / pyright / pre-commit / CI skeleton
* ディレクトリ骨格と `domain/protocols.py`（空定義で可）

### Phase 1: I/O + 初期生成

* pydantic v2 ローダ（全 CSV、行番号付きエラー）
* `PopulationArrays` と domain ↔ 並列配列のコンバータ
* `family_type_group` yaml マッピング
* ランダム初期人口生成
* `synthpop-jp quickstart` / `synthpop-jp validate-config`

### Phase 2: SA MVP

* 目的関数 minimal 版（原論文準拠モード、差分更新）
* age-change 遷移
* SA runner、`trace.jsonl`、`rich.live` 進捗
* `--resume` / checkpoint
* pytest-benchmark、hypothesis property test

### Phase 3a: Murata 拡張

* age-swap / hybrid
* family type × role × sex 分布からの年齢サンプリング
* extended objective（21 統計、原論文式(3)）
* 初期生成の 21 統計誤差 0 化

### Phase 3.5: 評価器骨格（Phase 3a と一部並列）

* `Evaluator` Protocol と `evaluate/` skeleton
* 統計別 L1 誤差レポータ（Table 13 形式）
* **CAP 先行実装**（DCR より先）
* rare cell 監視メトリクス
* `metrics.json` スキーマ + `report.md` テンプレート

### Phase 3b: 比較 runner

* `synthpop-jp compare`
* seed 群 runner、Welch's t + Holm、bootstrap CI
* 実験 1 / 2 を `paper_results/` に固定

### Phase 4: 評価器本体（utility / privacy を並列）

* broad utility: mixed-type 相関、全属性ペア TV、Frobenius 差
* narrow utility: 固定 3 タスクの TSTR/TRTS
* privacy: rare cell → CAP（既済）→ DCR/NNDR/ARD → MIA skeleton
* `report.md` ジェネレータに出典・ライセンス注記を自動埋込
* mkdocs サイト v0.2（日英併記）

### Phase 5: 改善ループ

* `improve/strategy.py` の 3 戦略（rule_based / pareto / random_search）
* multi-trial runner、best config 選択
* Pareto 可視化
* 実験 3 / 4
* MIA 実装（TAPAS / DOMIAS、stretch）

### Phase 6: v1.0 準備（新設）

* `paper_results/` 固定と `Makefile` による再現
* Zenodo 連携、DOI 発行、`CITATION.cff` 更新
* 英語ドキュメント完備
* SDV 比較 end-to-end ベンチ
* v1.0 release & PyPI stable

## 17. CLI 仕様

エントリポイントは `synthpop-jp`（`[project.scripts]` に登録）。`uvx` で一発起動可能にする。

```bash
# 30 秒 Quickstart（sample_case ダミーで end-to-end）
uvx synthpop-jp quickstart

# config バリデーションのみ
synthpop-jp validate-config --config configs/base.yaml

# 生成
synthpop-jp generate --config configs/base.yaml
synthpop-jp generate --config configs/base.yaml --resume outputs/run_001
synthpop-jp generate --config configs/base.yaml --dry-run
synthpop-jp generate --config configs/base.yaml --log-level DEBUG

# 評価
synthpop-jp evaluate --run-dir outputs/run_001

# 改善
synthpop-jp improve --config configs/base.yaml --trials 10

# 比較
synthpop-jp compare --experiment configs/compare_age_change_swap.yaml
```

共通フラグ:

* `--resume <run-dir>` … `artifacts/checkpoint/` から再開
* `--dry-run` … 設定解決と I/O 準備のみで終了
* `--log-level {DEBUG,INFO,WARNING,ERROR}` … stdout は `rich` 人間可読、`run.log` は JSON Lines

`--config` 未指定時は同梱デフォルト config を使う。

## 18. 設定ファイル例

config は pydantic v2 モデル（`config.py` の `GenerateConfig`, `AnnealingConfig`, `ObjectiveConfig`, `ImproveConfig`）で定義し、`extra="forbid"` で未定義キーを禁止する。`synthpop-jp validate-config` でチェックのみ走る。

```yaml
seed: 42
input_dir: data/sample_case
output_dir: outputs/run_001

annealing:
  transition: hybrid             # age_change | age_swap | hybrid
  initial_temperature: 10.0
  cooling_rate: 0.9995           # 0 < alpha < 1
  max_iters: 200000
  evals_per_agent: 1000
  p_change: 0.7
  p_swap: 0.3

objective:
  mode: paper                    # paper | research_extended
  use_extended_statistics: true
  weights:                       # mode=research_extended でのみ有効
    father_child_gap: 1.0
    mother_child_gap: 1.0
    couple_gap: 1.0
    demographic: 0.5
    family_type_demographic: 1.5
  entropy_regularization: false  # §11.6、mode=research_extended でのみ有効
  lambda: 0.0

improve:
  enabled: true
  trials: 10
  strategy: rule_based           # rule_based | pareto | random_search
```

### 18.1 seed の階層 spawning

```python
root_ss = np.random.SeedSequence(config.seed)
init_rng, sa_rng, eval_rng = root_ss.spawn(3)
trial_seeds = root_ss.spawn(config.improve.trials)
```

`metrics.json` に `seed`, `numpy_version`, `git_sha`, `uv.lock` のハッシュを必ず記録する。

## 19. テスト仕様

### 19.1 単体テスト

* family type から household template が正しく構築される
* objective 計算が期待値通り
* 遷移後も household size が不変
* age-swap 後に対象 2 人の age が交換される
* ハード制約（§11.5）が正しく検出される

### 19.2 結合テスト

* generate CLI が正常終了する
* SA 実行で best score が初期値から閾値以下に収束する（例: 初期 score の 30% 以下）
* evaluate CLI が metrics を出力する
* improve CLI が複数 trial を完走する

### 19.3 決定性テスト（回帰とは分離）

* **同一 seed・同一 input → 同一 `best_score`（bitwise 一致）**
* `uv.lock` 固定 + CI `uv sync --frozen`
* 失敗時は `paper_results/` の `metrics.json` との差分を出す

### 19.4 許容幅テスト

* 依存更新時の揺らぎ対応として **`best_score ±1%`** の幅で判定（決定性テストとは分離）
* utility 指標は `paper_results/` との相対差 5% 以内

### 19.5 Property テスト（hypothesis）

* 遷移後の household size 不変
* age-swap 後に 2 人の age が厳密に交換される
* 差分更新と全再計算の結果が一致する

## 20. 成果物

* `src/synthpop_jp/` 実装コード
* `tests/`
* `data/sample_case/`（完全合成ダミー、e-Stat 実データは同梱しない）
* `configs/`
* `outputs/example_run/`
* `paper_results/`（実験 1〜4 の固定出力、`Makefile` で再現）
* **`LICENSE`**（Apache-2.0）
* `NOTICE`（依存ライブラリのクレジット）
* `README.md`（日本語 primary、英語セクション併記、30 秒 Quickstart、比較表）
* **`CITATION.cff`**（Murata 2017 + Harada 2024 を preferred-citation、Zenodo DOI は v0.1 公開時）
* **`CHANGELOG.md`**（Keep a Changelog 形式、SemVer、v0.x 中の破壊的変更は明示）
* **`CODE_OF_CONDUCT.md`**（Contributor Covenant）
* **`CONTRIBUTING.md`**（新 family_type / 評価器追加の 10〜20 行例、worktree 規約）
* **`DATASET.md`**（e-Stat 利用規約、sample_case 由来、出典表示義務）
* `pyproject.toml`, `uv.lock`
* `Makefile`（`make quickstart`, `make paper`, `make docs`）
* `docs/spec/spec.md`（本書）
* `docs/spec/data_contract.md`
* `docs/spec/metrics.md`
* `docs/spec/experiment_report_format.md`
* `docs/experiment_plan.md`
* `docs/assumptions.md`
* `docs/adr/0001-internal-representation.md` 〜 `0004-naming-and-license.md`

## 21. 実装上の注意

1. まずは実統計ではなく、整合が取りやすい小規模ダミー統計で作る。
2. 年齢・役割の矛盾は目的関数ではなく **ハード制約** として遷移前に弾く（§11.5）。
3. 目的関数を一度に増やしすぎず、minimal → extended の順で広げる。
4. 評価を後回しにしない。`Evaluator` Protocol は Phase 3.5 で評価器骨格を先出しする。
5. 乱数 seed、設定ファイル、実験結果保存を初期から標準化する。
6. SA 内部表現は **NumPy 並列配列 + 差分更新**で固定する（ADR-0001）。
7. 将来の DP 拡張に備え、`Distribution` / `PrivacyMetric` Protocol は空で良いので §9 に置いておく（Priv S7）。

## 22. 判断基準

* 小規模統計入力から矛盾の少ない合成人口を生成できる
* `age-change` / `age-swap` / `hybrid` の比較ができる
* 統計整合性・有用性・秘匿性（proxy / CAP / MIA の 3 層）を同時に出せる
* 評価結果に応じて設定を更新するループ（rule_based / pareto / random_search）が回る
* 追加データや追加評価器を `entry_points` / Protocol で差し込める
* 同一 seed で bitwise 一致の再現性を確認できる

## 23. Claude Code への実装指示

1. `docs/spec/spec.md`（本書）と `docs/adr/0001`〜`0004` を読み、前提・スコープを明文化する
2. `docs/tasks/phase-NN/task-MMM.md` の設計に従い作業する
3. Phase 0 を先に完了し、仕様・基盤・ADR を凍結する
4. Phase 1〜2 で最小動作を確認する
5. その後に Murata 2017 拡張部分（Phase 3a / 3.5 / 3b）を追加する
6. 各 Phase ごとに、
   * 変更ファイル一覧
   * 実装内容
   * テスト結果
   * 残課題
     を `docs/reports/` に記録する
7. 実装完了後、`outputs/example_run/` にサンプル結果を保存する
