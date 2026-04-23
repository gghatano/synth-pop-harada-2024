# Assumptions（評価用実個票・倫理・利用規約）

**ステータス: 骨子（Phase 1 着手前に基本方針確定、Phase 3.5 で評価実行前に完全確定）**

本ドキュメントは `synthpop-jp` が **秘匿性評価（§13.3）で必要となる評価用実個票の protocol と倫理要件** を記述する。`docs/spec/spec.md` §13.3 および §6 から本書に委譲されている。

## 背景

DCR / NNDR / ARD / CAP / MIA のどれも「評価用の実個票 (individual-level records)」を前提とする。ところが Murata 2017 はそもそも「サンプル個票を使わず公開集計表のみから生成する」手法である。つまり本実装は、**生成入力**としては公開集計表のみを使うが、**評価入力**としては別途実個票が必要になる、という非対称性がある。

本書はこの非対称性を「何のデータを、どこから、どの手続きで得るか」で閉じる。

## 1. 評価用 "real" 個票 protocol（semi-synthetic 設定）

合成データ研究で標準的な **semi-synthetic 設定** を採用する:

1. 実個票データセット（例: ACS PUMS / IPUMS / e-Stat 公開ミクロデータ）から集計表を計算
2. 計算した集計表を `synthpop-jp` の入力として合成集団を生成
3. **元の実個票を hold-out として** DCR / CAP / MIA の評価に使う

これにより「生成器は実個票を一切見ていない」状態で評価が成立する。

**Phase 3.5 で hold-out 分割手順と cell size 制限を確定。**

## 2. 利用候補データセット

### 2.1 ACS PUMS（米国 American Community Survey Public Use Microdata Sample）

- 長所: 公開ミクロデータとして最も整備、研究利用前例多数
- 短所: 米国データであり日本の家族類型と完全一致しない
- ライセンス: Public Domain（USCB）
- 取得スクリプト: `scripts/fetch_acs_pums.py`（Phase 3.5 で作成）

### 2.2 IPUMS (International Public Use Microdata Series)

- 長所: 多国横断、日本分も一部あり
- 短所: 利用登録とデータ利用同意書が必要
- ライセンス: IPUMS Terms of Use
- 取得: 各研究者が個別申請

### 2.3 e-Stat 公開ミクロデータ / オーダーメード集計

- 長所: 日本の国勢調査と完全整合
- 短所: **個票の取得は厳格に制限**され、通常の研究用途では「オーダーメード集計」または「匿名データ」を利用する形になる
- ライセンス: 統計法 §33、§44、e-Stat 利用規約
- **本実装の評価用途としては原則使わない**（代わりに公開集計表から semi-synthetic 設定を組む）

**Phase 3.5 で最終選定。**

## 3. Hold-out 手順と cell size 制限

- 実個票から集計表を作成する際の **cell size ≥ 5** ルール（k-anonymity 下限）
- hold-out は random split ではなく **stratified**（family_type × sex × age_group 層別）
- hold-out 比率: 既定 20%

**Phase 3.5 で確定。**

## 4. IRB / data use agreement 要件

- ACS PUMS は原則 IRB 不要（公開データ）
- IPUMS は data use agreement 署名が必要
- 所属機関の IRB 必要性は **研究開始前に確認**
- 本書に「どのデータセット・どの版・誰が取得・取得日・IRB の有無」を記録

**テンプレートは §6 に記載。Phase 3.5 で使用時に記入。**

## 5. 統計法 §44・e-Stat 利用規約（出典表記義務）

e-Stat 由来の集計表を入力に使った場合は次の義務が発生する:

- **出典表示義務**（統計法 §44）
- **加工の明示**（e-Stat 利用規約）
- **商用再配布制限**（データによる、要個別確認）

本実装の対応:

- `io/writers.py` の `report.md` ジェネレータに **出典セクションを自動埋込**
- `DATASET.md` に e-Stat データ取得スクリプト (`scripts/fetch_estat.py`) と出典テンプレを同梱
- **`data/sample_case/` は完全合成ダミー** とし、e-Stat 実データは同梱しない（ADR-0004）

## 6. 倫理記録テンプレート

実験で特定の実個票データセットを使う際は、以下のメタデータを `docs/experiments/<date>-<slug>/metadata.yaml` に記録する:

```yaml
dataset:
  name: "ACS PUMS 2022"
  version: "2022 1-year"
  source_url: "https://www.census.gov/programs-surveys/acs/microdata/documentation.html"
acquisition:
  acquired_by: "researcher_name"
  acquired_at: "2026-04-23"
  license: "Public Domain (USCB)"
  irb_status: "not_required"
  dua_signed: false
hold_out:
  split_method: "stratified"
  split_ratio: 0.20
  stratify_columns: ["family_type", "sex", "age_group"]
  cell_size_floor: 5
```

**Phase 3.5 で実験記録時に使用。**

## 7. 履歴

- 2026-04-23: v0.0.1 骨子作成（Phase 0）
