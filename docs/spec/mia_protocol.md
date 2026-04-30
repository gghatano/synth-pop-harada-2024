# MIA (Membership Inference Attack) Protocol — Phase 5 実装の事前登録

このドキュメントは Phase 5 で実装する MIA 評価器の **設計・条件・判定基準** を実装前に固定するためのものです。Issue #100 の成果物として置き、Phase 5 着手時の再設計コストを下げます。

仕様変更があれば、このファイルへの PR として変更履歴を残します（実装後の事後変更は禁止）。

---

## 1. 何のための文書か（非技術者向け）

合成人口（公開統計だけを材料に作った人工データ）に対して、「ある実在の個人がそのデータの作成元に含まれていたか」を当てる攻撃を **MIA (Membership Inference Attack)** と呼びます。MIA に対する耐性は、合成データを公開して良いかどうかを判断する重要な指標です。

このドキュメントは、本リポジトリで MIA を実装するときに使う **計算手順・データ分割・しきい値判定** を、実装に入る前に固定するためのものです。事前登録（pre-registration）として記録し、結果を見てから判定基準を後付けで変えないようにします。

---

## 2. 想定する攻撃シナリオ

### 2.1 攻撃者の能力（threat model）

| 項目 | 内容 |
|---|---|
| 知識 | 合成データ全体（公開）と、対象個人 1 件の個票（既知） |
| 目的 | 対象個人が **訓練集合** に含まれていたか判定（YES/NO） |
| 計算リソース | 標準 PC、shadow training は許容（オフライン） |
| 知らないこと | 合成データ生成器の seed・温度スケジュール・内部状態 |

### 2.2 評価対象

合成人口生成器（本リポジトリの SA + extended objective）。`generate` で出力した `synthetic_persons.csv` が公開対象。

### 2.3 ベースライン

- **trivial baseline**: ランダム判定（AUC = 0.5）
- **distance baseline**: 距離（Gower）が閾値以下なら member 判定（DCR-based）
- **shadow MIA**: 後述の shadow training を使う（本 protocol の主役）

---

## 3. 採用する手法

Phase 5 で実装する MIA は **TAPAS (Houssiau et al. 2022)** と **DOMIAS (van Breugel et al. 2023)** の 2 種類を並べて報告します。

| 手法 | 仕組み | 必要データ | 主指標 |
|---|---|---|---|
| **TAPAS** | shadow seed 群で member/non-member の合成データを多数作り、対象個人の周辺密度を統計的に検定 | shadow training (≥ 50 seed) | AUC, TPR @ low FPR |
| **DOMIAS** | 合成データ密度 ÷ 参照分布密度 の比率で判定（density estimation 経由） | shadow training (≥ 50 seed) | AUC, TPR @ FPR=0.1 |

### 3.1 共通の前提

- **target set**: real 個票から無作為に N_target 件抽出（既定 N_target = 100）
- **member set**: target のうち、生成パイプラインに **入力した** 個人（半分: 50 件）
- **non-member set**: 残り 50 件（入力していない）
- 生成器は member set を含むように **input statistics** を構成する
  - 注意: 本実装は微個票で訓練しないため、member の影響は marginal 統計を通じてしか伝わらない。これが MIA 耐性の上限を上げる効果を持つ前提

### 3.2 shadow training の構成

| パラメータ | 値 |
|---|---:|
| shadow seed 数 | 50 |
| 各 shadow の synth 規模 | 1,000 世帯 |
| 各 shadow の SA 反復数 | 200,000 |
| target 個人を含む shadow の割合 | 半数（25 個） |
| target 個人を含まない shadow の割合 | 半数（25 個） |

50 seed × 200,000 = 1,000 万 SA step。1,000 世帯規模なら現状ベンチで 5.2 秒/seed なので合計 **約 4 分**（並列化なしの楽観値）。

---

## 4. データ分割

### 4.1 holdout 構成

```
real microdata (N_real)
├── target set         (100 件、ID 固定)
│   ├── member         (50 件)
│   └── non-member     (50 件)
└── reference (rest)   (N_real - 100 件、shadow training の参照集合)
```

### 4.2 split の seed 固定

- `holdout_seed = 12345` で固定
- target 抽出は決定論的（`np.random.default_rng(holdout_seed).choice(N_real, 100, replace=False)`）
- target の中で member / non-member を分ける split は `member_split_seed = 67890` で固定

---

## 5. しきい値判定

### 5.1 主指標: AUC

各手法の出力スコア `s_i` を target 全件で取り、ROC 曲線下面積（AUC）で判定する。

- AUC = 0.5: 攻撃成功率はランダム
- AUC = 1.0: 完全に member/non-member を識別

### 5.2 補助指標: TPR @ low FPR

ROC の左端（FPR が低い領域）での True Positive Rate。具体的には:

- TPR @ FPR = 0.01
- TPR @ FPR = 0.1

低い FPR（誤って non-member を member と判定する確率が小さい領域）での TPR は、実用上の攻撃成功率に近い。

### 5.3 失格判定

- **AUC ≤ 0.55** → 「実用 MIA は困難」と報告
- **AUC > 0.7 または TPR@FPR=0.1 > 0.5** → 「合成データは MIA に対し脆弱」と警告し、`report.md` の §6 (MIA) に追記

### 5.4 結果を見てから閾値を変えない

事前登録：上記 5.3 の判定基準は **本 protocol の凍結対象**。実験結果が出てから閾値を緩める / 厳しくするのは禁止（後付け合理化の防止）。

---

## 6. 出力スキーマ

`metrics.json` への追加キー:

```json
{
  "mia.tapas.auc": 0.52,
  "mia.tapas.tpr_at_fpr_001": 0.04,
  "mia.tapas.tpr_at_fpr_010": 0.13,
  "mia.domias.auc": 0.56,
  "mia.domias.tpr_at_fpr_001": 0.05,
  "mia.domias.tpr_at_fpr_010": 0.18,
  "mia.shadow_seed_count": 50
}
```

`report.md` に **§5「MIA (shadow-based)」** セクションを追記する（Issue #101 の citation 自動埋込と組み合わせ、TAPAS / DOMIAS の出典を明記）。

---

## 7. 実装疑似コード

```python
# Phase 5 実装の指針（Phase 4b では実装しない）

def evaluate_mia_tapas(
    real_microdata: PopulationArrays,
    *,
    n_target: int = 100,
    n_shadow: int = 50,
    holdout_seed: int = 12345,
    member_split_seed: int = 67890,
    shadow_synth_n_households: int = 1000,
    shadow_max_iters: int = 200_000,
) -> MiaResult:
    """TAPAS による MIA 評価器の擬似コード."""
    # 1) target を抽出（holdout_seed で固定）
    target_idx = np.random.default_rng(holdout_seed).choice(
        real_microdata.n_persons, n_target, replace=False
    )
    target = subset(real_microdata, target_idx)

    # 2) member / non-member に二分（member_split_seed で固定）
    is_member = np.random.default_rng(member_split_seed).choice(
        n_target, n_target // 2, replace=False
    )

    # 3) shadow training: n_shadow 個の合成データを作る
    #    half は member を含む input statistics で生成、
    #    half は non-member のみで生成
    shadows: list[ShadowResult] = []
    for k in range(n_shadow):
        contains_member = (k < n_shadow // 2)
        synth = generate_synthetic(
            target_microdata=target if contains_member else target[~is_member],
            n_households=shadow_synth_n_households,
            max_iters=shadow_max_iters,
            seed=k,
        )
        shadows.append(ShadowResult(synth=synth, contains_member=contains_member))

    # 4) target 各個人について TAPAS スコアを計算
    #    member shadow と non-member shadow での尤度比に基づく
    scores = []
    labels = []
    for i, target_record in enumerate(target):
        s = tapas_likelihood_ratio(target_record, shadows)
        scores.append(s)
        labels.append(1 if i in is_member else 0)

    # 5) AUC と TPR@FPR を計算
    return MiaResult(
        auc=roc_auc_score(labels, scores),
        tpr_at_fpr=tpr_at_target_fpr(labels, scores, target_fprs=[0.01, 0.1]),
    )
```

DOMIAS 版は手順 4 を **density estimation の比率** に置き換えれば同型に書ける（詳細は van Breugel et al. 2023）。

---

## 8. 実装上の留意点

### 8.1 計算量

- 50 seed × 200,000 反復 = 1,000 万 step。並列化（multiprocessing）で 5–10 倍高速化が現実的
- shadow training の中間結果（`synthetic_persons.csv` など）は `artifacts/mia_shadows/` に保存し、resume 可能にする

### 8.2 再現性

- 全 seed を `holdout_seed`, `member_split_seed`, `shadow_seeds = range(n_shadow)` の 3 系統に分解
- 結果は `metrics.json` + `mia_report.json`（個別 shadow ごとの中間結果）に書き出す

### 8.3 倫理

- target に使う real microdata は **完全に合意取得済み**（公開統計のみ、または研究目的の利用許諾を得たもの）
- 本実装の sample_case は **完全ダミー** で、MIA 評価には使えない（実験用に別途 hold-out を用意する）

---

## 9. 関連

- 親 Issue: #100（本ドキュメントの作成）
- 後続 Issue: Phase 5 で本 protocol に基づく MIA 実装（TAPAS / DOMIAS）
- 参考論文:
  - Houssiau, F. et al. (2022). "TAPAS: a Toolbox for Adversarial Privacy Auditing of Synthetic Data". arXiv:2211.06550
  - van Breugel, B. et al. (2023). "Membership Inference Attacks against Synthetic Data through Overfitting Detection (DOMIAS)". AISTATS
  - Stadler, T., Oprisanu, B., Troncoso, C. (2022). "Synthetic Data – Anonymisation Groundhog Day". USENIX Security
- 関連 spec: `docs/spec/spec.md` §13.3 (c) shadow-based MIA、`docs/reviews/review-privacy.md` 指摘 2

---

## 10. このドキュメントの位置付け

- **このファイル**: Phase 5 実装の **事前登録**。条件・データ・判定基準を凍結
- **Phase 5 の実装 PR**: 本 protocol に従った実装 + 1 つの実例レポート（`experiments/<日付>-mia-shadow-baseline/`）
- **改訂手順**: 実装前なら PR で本ファイルを書き換えて再合意。**実装後は変更禁止**（実験結果に応じた閾値変更を防ぐ）
