# 計画: Issue #99 — DCR / NNDR / ARD 評価器

対象 Issue: #99
計画作成日: 2026-04-30
派生元: develop @ `f94d925`（#98 Gower / #101 citation merge 後）

---

## 1. 再確認: 成功条件

| 成功条件 | 担保方法 |
|---|---|
| DCR / NNDR / ARD の 3 評価器が PrivacyMetric Protocol に準拠 | `evaluate(synthetic, holdout) -> dict[str, float]` シグネチャ |
| hold-out split が seed 固定で再現可能 | 評価器 `__init__(seed=...)` |
| ARD は Harada 2024 出典が `report.md` に自動埋込 | `_CITATIONS` の "ard." prefix 追加（#101 と連携） |
| sample_case で 3 指標が `metrics.json` に出力される | CLI 統合 + 結合テスト |
| CAP/TCAP との数値矛盾が無い sanity check | ユニットテスト |

## 2. 設計方針

### 2.1 各指標の定義（Harada 2024 §5.2 / metrics.md §5.1）

| 指標 | 定義 | 値域 |
|---|---|---:|
| **DCR** (Distance to Closest Record) | 各 synth レコードについて real 集合の最近傍距離。p05 や mean を出す | [0, 1] |
| **NNDR** (Nearest Neighbor Distance Ratio) | 最近傍距離 / 2 番目近傍距離。低い値ほど「真似している」 | [0, 1] |
| **ARD** (Average Record Distance, Harada 2024) | synth × real の Gower 距離平均 | [0, 1] |

### 2.2 共通入力

`gower_distance_matrix(synth, real, is_numeric=...)` で N×M 距離行列を計算（#98 で実装済み）。

### 2.3 評価器 API

```python
class DCREvaluator:
    name = "dcr"
    layer: PrivacyLayer = "proxy"
    
    def evaluate(self, synthetic, holdout) -> dict[str, float]:
        # → {"dcr.p05", "dcr.p50", "dcr.mean"}

class NNDREvaluator:
    name = "nndr"
    ...

class ARDEvaluator:
    name = "ard"
    ...
```

すべて `synthpop_jp/evaluate/privacy_metrics.py` に同居（Phase 4b の 3 兄弟）。既存 `privacy_metrics.py` は stub なので置き換え。

### 2.4 出典追加

`reports/markdown.py` の `_CITATIONS` に追加:

```python
("dcr.", "Lampe (2018) 'Synthetic Data Vault'... DCR, distance to closest record"),
("nndr.", "Platzer & Reutterer (2021) 'Holdout-Based Empirical Assessment'... NNDR"),
("ard.", "Harada 2024 §5.2 ARD (Average Record Distance, Gower 距離平均)"),
```

## 3. 実装方針

### 追加するファイル

無し（既存 `privacy_metrics.py` を実装）

### 変更するファイル

- `src/synthpop_jp/evaluate/privacy_metrics.py`: 3 評価器を実装
- `src/synthpop_jp/cli.py`: `--real-persons-csv` で 3 評価器を呼ぶ
- `src/synthpop_jp/reports/markdown.py`: `_CITATIONS` に 3 prefix 追加
- `tests/evaluate/test_privacy_metrics.py` 新規

### 着手順

1. **Cycle 1**: `DCREvaluator` の RED テスト → 実装
2. **Cycle 2**: `NNDREvaluator` の RED テスト → 実装
3. **Cycle 3**: `ARDEvaluator` の RED テスト → 実装
4. **Cycle 4**: 出典 prefix 追加 → markdown テスト
5. **Cycle 5**: CLI 統合 → 結合テスト

## 4. テスト観点

- [ ] DCR: synth=real のとき各 synth の最近傍距離 0
- [ ] DCR: synth と real が完全分離（全レコードが Gower=1）のとき最近傍 1.0
- [ ] NNDR: synth=real（重複あり）のとき NNDR=0/0 → 0 で扱う
- [ ] NNDR: 値域 [0, 1]
- [ ] ARD: synth=real のとき ARD = mean(対称行列の平均) = 0 ではない（self-pair でも 1 ペアあたり 0 が混じるが N×N で平均）
- [ ] 全評価器が PrivacyMetric Protocol に準拠
- [ ] 各キーが `metrics.json` に出力される（CLI 経由）

## 5. リスクと代替案

### 失敗モード

- **計算量**: N×M = 1000×1000 で 2 秒、1万×1万で 200 秒。sample_case は 100 オーダーなので問題なし
- **ARD の正規化**: Gower 距離自体が [0, 1] なので追加正規化不要

### Plan B

Issue #99 の出典 prefix 追加は #101 が merge 済みなので問題なし。

## 6. worktree

- worktree: `gitworktree/feature-99-dcr-nndr-ard/`
- branch: `feature/99-dcr-nndr-ard`
- 派生元: `origin/develop` @ `f94d925`（#98 + #101 merge 後）

## 7. レビュー段階で確認したい論点

- DCR の集約（p05 / p50 / mean）の選び方
- NNDR で「2 番目近傍距離」が同距離のときの挙動
- ARD の計算（synth × real 全ペア vs synth のみ最近傍）
