# Metrics（距離・評価指標の仕様）

**ステータス: 骨子（Phase 3〜4 で肉付け）**

本ドキュメントは `synthpop-jp` が報告する全評価指標の距離定義・算出式・アルゴリズムを一元化する。`docs/spec/spec.md` §13 から本書に委譲されている。

## 1. 距離の基本方針

- **Gower 距離を primary** にする（混合型データの標準的手法）
- 連続変数（age 等）は [0, 1] に正規化してから距離を取る
- カテゴリ変数（sex, role, family_type 等）はマッチ / 非マッチで 0 / 1
- Euclidean は使わない（カテゴリ変数混在で不適切）
- `domain/distance.py` に `gower(x, y, col_types)` を実装し、unit test を置く

**Phase 4 冒頭で実装。**

## 2. 統計整合性指標

- **L1 (= 原論文式(1) の絶対誤差) を primary**
- L2 / χ² を secondary
- TV を参考指標とする
- 人口ピラミッドは **1 歳刻みと 5 歳刻みの両方**を報告（原論文が両方使うため）
- 21 統計の Table 13 形式ブレークダウンを `aggregate_metrics.py` で出力

**Phase 3.5 で実装開始、Phase 3b で完成。**

## 3. Broad utility 指標

- 単変量分布差: L1 / TV
- クロス集計差: 全属性ペア TV、Frobenius norm と max-abs の両方
- **混合型相関行列** は `dython.associations` 準拠
  - 連続 × 連続: Pearson
  - カテゴリ × カテゴリ: Cramér's V
  - 連続 × カテゴリ: Correlation Ratio
  - 非対称関連（方向あり）: Theil's U
- 相関差は Frobenius norm / max-abs の両方を出す

**Phase 4a で実装。**

## 4. Narrow utility 指標

**固定 3 タスク**（Phase 0 で凍結、事後変更禁止）:

- タスク A: family_type 分類（age, sex, 世帯内 role 分布 → family_type、**macro-F1**）
- タスク B: 世帯人数回帰（family_type, 子ども人数 → household_size、**RMSE**）
- タスク C: 役割予測（age, sex, family_type → role、**macro-F1**）

評価:

- **TSTR**（Train Synthetic, Test Real）
- **TRTS**（Train Real, Test Synthetic）
- 両方を seed 群 n=10〜30 で平均 ± SD + bootstrap CI

データ分割・学習アルゴリズム・ハイパラは `docs/experiment_plan.md` に事前登録して凍結する。

**Phase 4a で実装。**

## 5. Privacy 指標 3 層

### 5.1 (a) 類似度 proxy（MVP、Phase 4）

距離定義:

- **Gower 距離**（§1）を使う
- 評価用 real 個票と生成合成集団の間で計算する

指標:

- **DCR** (Distance to Closest Record): 各 real レコードから最も近い合成レコードまでの Gower 距離。分布（min / 5 percentile / median）を報告
- **NNDR** (Nearest Neighbor Distance Ratio): 最近傍距離 / 次近傍距離の比
- **ARD** (Average Record Distance): Harada 2024 由来の平均レコード距離指標（Phase 4 で厳密定義を確定）

**本層は proxy に過ぎない旨を `report.md` に明記**（Ganev & De Cristofaro 2024）。

### 5.2 (b) 属性推論 baseline（MVP 必須、Phase 4 / Phase 3.5 先行）

- **Generalized CAP** (Correct Attribution Probability、Taub et al. 2018)
  - quasi-identifier `Q` と sensitive attribute `S` を定める
  - 合成集団から推定される `P(S | Q=q)` と、real 個票の `S` の一致確率を評価
- **TCAP** (Targeted CAP)
- Per-family_type CAP 分解も出力

アルゴリズムの詳細は Phase 3.5 で確定。

### 5.3 (c) shadow-based MIA（Phase 5 stretch）

- **TAPAS** (Houssiau et al. 2022): shadow generator を異なる seed で再生成して MIA 成功率を推定
- **DOMIAS** (van Breugel et al. 2023)
- shadow seed 群の運用は `docs/experiment_plan.md` に事前登録

**Phase 5 で実装。**

## 6. Rare cell 監視

- `family_type × age` で cell size < 5 の **割合**
- **unique 率**（1 人しかいない cell の割合）
- 属性別分解（per family_type）
- `evaluate/rare_cell_metrics.py` に実装

**Phase 3.5 で実装。**

## 7. 出典・参考文献

- Gower (1971) "A general coefficient of similarity and some of its properties"
- Ganev & De Cristofaro (2024) "On the Inadequacy of Similarity-based Privacy Metrics" arXiv:2312.03054
- Houssiau et al. (2022) "TAPAS"
- van Breugel et al. (2023) "DOMIAS" ICML
- Taub et al. (2018) "Differential Correct Attribution Probability"
- Harada et al. (2024)（`docs/papers/harada_2024.pdf`）

**Phase 4 で完全な参考文献リスト化。**

## 8. 履歴

- 2026-04-23: v0.0.1 骨子作成（Phase 0）
