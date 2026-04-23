# Spec: Murata 2017 と「生成・評価・改善」型の合成人口データ実装

## 1. 背景

本実装の目的は、公開統計から世帯・個人レベルの合成人口データを生成する Murata et al. (2017) の simulated annealing (SA) ベース手法を、Python で再現可能な形で実装し、その上に「生成→評価→改善」の反復ループを載せることで、実験可能な研究用プロトタイプを構築することである。

Murata 2017 は、サンプル個票を使わず、公開統計に整合する世帯構成・個人属性を SA で探索的に再構成する手法である。候補解遷移として `age-change` と `age-swap` を比較し、探索回数が少ないときは age-change が有利、十分な探索回数があるときは age-swap が有利であることを報告している。目的関数は統計表との差の総和であり、初期集団生成・候補解遷移・追加統計による評価の3点が改良点として示されている。

一方、合成人口は公開集計表から数値計算を繰り返して差を最小化する探索的生成が有力であり、単発生成ではなく、複数データセットを生成・評価しながら利用する前提が適している。本 Spec では、Murata 2017 の再現をコア実装とし、その外側に「生成・評価・改善」ループを設ける。

## 2. 目的

### 2.1 主目的

1. 公開統計を入力として、世帯・個人属性を持つ合成人口データを生成できること。
2. Murata 2017 の `age-change` / `age-swap` を切り替えて比較できること。
3. 生成結果を統計整合性・有用性・秘匿性の観点で評価できること。
4. 評価結果を用いて、次の生成条件を自動更新する改善ループを持つこと。
5. 小規模ダミーデータで end-to-end 実行できること。

### 2.2 副目的

* 都道府県統計や仮想都市データに差し替えやすい構成にする。
* 将来、TAPAS 等による MIA/AIA 評価を追加できるようにする。
* 生成された複数候補を保存し、比較レポートを出せるようにする。

## 3. 非目的

以下は今回のスコープ外とする。

* 日本の実統計表を完全収集して全国再現すること
* 高速化の最適化（C++化、GPU化、分散実行）
* GUI の実装
* 差分プライバシー保証付き生成器の実装
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
* 個票レベルの近傍類似度評価
* 必要に応じて推定タスク性能評価
* 実験メタデータ保存

### 4.3 改善器

* 遷移方式変更（age-change / age-swap / 混合）
* 温度スケジュール変更
* 目的関数重み変更
* 初期解生成パラメータ変更
* 停止条件の延長・短縮

## 5. 参照手法の要点

### 5.1 Murata 2017 の実装要点

Murata 2017 は、9種類の家族類型、子ども人数統計、人口ピラミッド、親子年齢差、夫婦年齢差などの公開統計を用い、SA により誤差を最小化する。元の9統計ベース目的関数 `f(A)` と、拡張後の21統計ベース目的関数 `f'(A)` が示されている。候補解遷移としては、

* `age-change`: 役割に応じた年齢分布に従い1人の年齢を変更
* `age-swap`: 同一 family type・同一 sex の2人の年齢を交換

の2方式がある。`age-swap` は family type 別人口構成を保ちやすい。

### 5.2 生成・評価・改善の考え方

本実装では「一度生成して終わり」ではなく、評価に基づく再生成を前提とする。

### 5.3 評価観点

* 統計整合性
* 有用性（broad utility / narrow utility）
* 秘匿性（近傍距離、レコード一致、必要に応じて MIA/AIA）

## 6. システム要件

### 6.1 開発言語・環境

* Python 3.11 以上
* パッケージ管理: `uv`
* 実装形態: ライブラリ + CLI
* OS: Linux / macOS を想定

### 6.2 想定ライブラリ

* `pandas`
* `numpy`
* `scipy`
* `pydantic`
* `typer`
* `matplotlib`
* `pyyaml`
* `rich`
* `scikit-learn`

## 7. 入出力仕様

### 7.1 入力

#### 必須入力

1. `family_type_counts.csv`

   * family_type
   * household_count

2. `children_count_dist.csv`

   * family_type_group
   * n_children
   * rate

3. `demographic_by_age_sex.csv`

   * sex
   * age
   * count

4. `age_diff_parent_child.csv`

   * relation_type
   * diff_bin
   * rate_or_count

5. `age_diff_couple.csv`

   * diff
   * rate_or_count

#### 任意入力

6. `demographic_by_family_type_role.csv`

   * family_type
   * sex
   * role
   * age
   * count

7. `household_size_by_family_type.csv`

   * family_type
   * household_size
   * count

8. `config.yaml`

### 7.2 出力

1. `synthetic_households.csv`
2. `synthetic_persons.csv`
3. `metrics.json`
4. `report.md`
5. `artifacts/`

## 8. データモデル

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

```text
src/
  synthetic_population/
    config.py
    io/
      loaders.py
      writers.py
    domain/
      household.py
      person.py
      statistics.py
    init/
      household_sampler.py
      initial_population.py
    optimize/
      objective.py
      annealing.py
      transitions.py
      cooling.py
    evaluate/
      aggregate_metrics.py
      privacy_metrics.py
      utility_metrics.py
      downstream_tasks.py
    improve/
      tuner.py
      strategy.py
    experiments/
      runner.py
      comparison.py
    cli.py
```

## 10. 生成ロジック仕様

### 10.1 初期集団生成

1. family type 別に世帯数を生成
2. 各 family type に household size を割当
3. children を持つ family type に子ども人数を割当
4. role を household template から展開
5. sex を role に応じて設定
6. age を粗い人口ピラミッドまたは family type × role × sex 分布から初期割当

### 10.2 初期集団生成の方針

* 再現性のため乱数 seed を固定可能にする
* 制約違反がある場合は household 単位で再生成する
* まずは小規模データで矛盾なく生成できることを優先する

## 11. 目的関数仕様

### 11.1 基本方針

目的関数は「公開統計と生成結果の差の総和」を基本とする。

### 11.2 第一段階: minimal objective

* father-child 年齢差誤差
* mother-child 年齢差誤差
* couple 年齢差誤差
* male demographic pyramid 誤差
* female demographic pyramid 誤差

### 11.3 第二段階: extended objective

family type 別 demographic pyramid まで拡張する。

### 11.4 式の実装方針

```text
objective = sum_s sum_j weight_s * abs(observed[s,j] - target[s,j])
```

### 11.5 追加ペナルティ

* 年齢が 0〜100 を外れた場合の禁止ペナルティ
* role と年齢の矛盾ペナルティ
* 親が子より若い場合の大ペナルティ
* 夫婦の片方が未成年の場合の大ペナルティ

## 12. SA 仕様

### 12.1 共通

* 初期温度 `T0`
* 冷却率 `alpha`
* 反復数 `max_iters`
* 評価回数 / person 上限
* 受理判定: Metropolis

### 12.2 遷移方式

#### A. age-change

* family type を選択
* member を選択
* 役割に応じた分布から新年齢をサンプル
* 年齢を更新

#### B. age-swap

* family type と sex を選択
* 対応する2人を選択
* 年齢を交換

#### C. hybrid

* `p_change` と `p_swap` で混合
* 初期探索では `age-change` を厚め、後半は `age-swap` を厚めにする設定を可能にする

### 12.3 停止条件

* `iter >= max_iters`
* `evals_per_agent >= limit`
* `best_score <= target_threshold`
* `patience` 期間改善なし

## 13. 評価仕様

### 13.1 統計整合性評価

* 総目的関数値
* 統計別誤差
* 平均絶対誤差
* 相対誤差
* 人口ピラミッド差分
* family type 別人数差分

### 13.2 有用性評価

#### Broad utility

* 単変量分布差
* クロス集計差
* 相関差
* Jensen-Shannon 距離または TV 距離

#### Narrow utility

ダミー目的変数を用意し、

* 実データ学習 → 実データ評価
* 合成データ学習 → 実データ評価

の性能差を比較する。

### 13.3 秘匿性評価

#### 初期実装

* 最近傍距離 (DCR)
* NNDR
* レコード一致率
* 属性部分一致率
* ARD

#### 拡張候補

* TAPAS による MIA
* TAPAS による AIA
* holdout distinguishing
* shadow modelling

## 14. 生成・評価・改善ループ

### 14.1 ループ概要

```text
for trial in trials:
    generate initial population
    optimize with SA
    evaluate utility/privacy/statistical fit
    record metrics
    update parameters
select best configuration
```

### 14.2 改善対象

* transition type
* cooling schedule
* objective weights
* max iterations
* household initialization heuristics

### 14.3 改善ロジック（初版）

* 親子年齢差誤差が大きい → `age-change` 比率を上げる
* demographic 誤差が小さいが親族関係誤差が大きい → `age-swap` を増やす
* 有用性が高いが近傍距離が小さすぎる → penalty または iteration 制限を調整
* 収束が遅い → 温度減衰を緩める

### 14.4 改善ロジック（将来）

* Bayesian optimization
* multi-objective optimization
* bandit による遷移選択

## 15. 実験計画

### 15.1 実験 1: Murata 再現の最小比較

* `age-change` と `age-swap` の傾向差を確認する
* 同一 seed 群
* 同一入力統計
* evals_per_agent を複数水準で変更

### 15.2 実験 2: hybrid 戦略

* 初期 `age-change`、後半 `age-swap` の混合が有効か確認する

### 15.3 実験 3: 生成・評価・改善ループの有効性

* 固定設定より改善ループのほうが総合評価が良いか確認する

### 15.4 実験 4: 複数候補生成

* 単一合成人口ではなく複数データセット生成時のばらつきを確認する

## 16. 実装フェーズ

### Phase 1: 骨組み

* プロジェクト初期化
* 入力ローダ
* ドメインモデル
* ダミー入力一式
* ランダム初期人口生成

### Phase 2: SA 最小実装

* 目的関数 minimal 版
* age-change 実装
* SA 実装
* ログ出力

### Phase 3: Murata 拡張

* age-swap 実装
* family type 別分布対応
* extended objective 実装
* 比較実験 runner 実装

### Phase 4: 評価

* broad utility
* 近傍ベース privacy proxy
* レポート出力

### Phase 5: 改善ループ

* rule-based tuner
* 複数 trial 実行
* best config 選択

## 17. CLI 仕様

```bash
uv run python -m synthetic_population.cli generate --config configs/base.yaml
uv run python -m synthetic_population.cli evaluate --run-dir outputs/run_001
uv run python -m synthetic_population.cli improve --config configs/base.yaml --trials 10
uv run python -m synthetic_population.cli compare --experiment configs/compare_age_change_swap.yaml
```

## 18. 設定ファイル例

```yaml
seed: 42
input_dir: data/sample_case
output_dir: outputs/run_001

annealing:
  transition: hybrid
  initial_temperature: 10.0
  cooling_rate: 0.9995
  max_iters: 200000
  evals_per_agent: 1000
  p_change: 0.7
  p_swap: 0.3

objective:
  use_extended_statistics: true
  weights:
    father_child_gap: 1.0
    mother_child_gap: 1.0
    couple_gap: 1.0
    demographic: 0.5
    family_type_demographic: 1.5

improve:
  enabled: true
  trials: 10
  strategy: rule_based
```

## 19. テスト仕様

### 19.1 単体テスト

* family type から household template が正しく構築される
* objective 計算が期待値通り
* 遷移後も household size が不変
* age-swap 後に対象2人の age が交換される
* 禁止制約が正しく検出される

### 19.2 結合テスト

* generate CLI が正常終了する
* SA 実行で best score が初期値以下になる
* evaluate CLI が metrics を出力する
* improve CLI が複数 trial を完走する

### 19.3 回帰テスト

* seed 固定時に主要メトリクスの大幅劣化がない

## 20. 成果物

* `src/` 実装コード
* `tests/`
* `data/sample_case/`
* `configs/`
* `outputs/example_run/`
* `README.md`
* `docs/spec.md`
* `docs/experiment_plan.md`
* `docs/assumptions.md`

## 21. 実装上の注意

1. まずは実統計ではなく、整合が取りやすい小規模ダミー統計で作る。
2. 年齢・役割制約を曖昧にすると収束しにくくなるため、禁止制約を先に入れる。
3. 目的関数を一度に増やしすぎず、minimal → extended の順で広げる。
4. 評価を後回しにしない。
5. 乱数 seed、設定ファイル、実験結果保存を初期から標準化する。

## 22. 判断基準

* 小規模統計入力から矛盾の少ない合成人口を生成できる
* `age-change` / `age-swap` / `hybrid` の比較ができる
* 統計整合性・有用性・秘匿性 proxy を同時に出せる
* 評価結果に応じて設定を更新するループが回る
* 追加データや追加評価器を差し込みやすい構成になっている

## 23. Claude Code への実装指示

1. `docs/spec.md` を読み、前提・スコープを明文化する
2. `docs/tasks/phase-01.md` から `phase-05.md` を作成する
3. Phase 1〜2 を先に完了し、最小動作を確認する
4. その後に Murata 2017 拡張部分を追加する
5. 各 Phase ごとに、

   * 変更ファイル一覧
   * 実装内容
   * テスト結果
   * 残課題
     を `docs/reports/` に記録する
6. 実装完了後、`outputs/example_run/` にサンプル結果を保存する

