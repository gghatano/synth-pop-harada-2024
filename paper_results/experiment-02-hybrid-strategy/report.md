# 実験 02 — hybrid 戦略

実施日: 2026-05-04
担当: Claude Code（Issue #115 phase-6）
コード: `paper_results/experiment-02-hybrid-strategy/run.py`

---

## 1. なにを確かめた実験か（非技術者向け）

実験 01 では「1 人の年齢を動かす」（age-change）と「2 人の年齢を入れ替える」（age-swap）の 2 つを比べました。本実験はこの 2 つを **確率的に混ぜた hybrid 戦略**（前半 age-change を多めに、後半 age-swap を多めに、線形に切り替える）が、単独の戦略より優れているかを確認します。

Murata 2017 の論文（§5.2）は、初期は age-change で広く探索し、後半は age-swap で局所構造を整えると、単独より総合得点が良くなると主張しています。

## 2. 実験条件

| 項目 | 値 |
|---|---|
| 入力データ | `data/sample_case/` (100 世帯) |
| 初期生成 | `use_zero_error_init=True` |
| 目的関数 | strict_extended (21 統計) |
| 戦略 | `age_change`, `age_swap`, `hybrid (LinearPChange 0.8 → 0.2)` |
| 冷却 | `ExponentialCooling(T0=1.0, alpha=0.999)` |
| `evals_per_agent` | 2000 (CI 既定) / 4000 (full) |
| seed | `[1, 2, 3]`（n=3、CI 既定） |
| 統計検定 | Welch's t + Holm-Bonferroni 補正 |

## 3. 結果

### 3.1 best_score 一覧（CI 既定 n=3 / 100 世帯 / evals=2000）

| seed | age_change | age_swap | hybrid |
|---:|---:|---:|---:|
| 1 | 453.0 | 567.0 | 453.0 |
| 2 | 455.0 | 570.0 | 455.0 |
| 3 | 453.0 | 568.0 | 453.0 |

### 3.2 Welch's t-test + Holm 補正

| 比較 | t | p-value (raw) | Holm 棄却 (α=0.05) |
|---|---:|---:|:---:|
| age_change vs age_swap | -103.72 | 0.0000 | yes |
| age_change vs hybrid   | 0.00    | 1.0000 | no |
| age_swap vs hybrid     | +103.72 | 0.0000 | yes |

age-swap だけが他 2 戦略から有意に高い best_score（=悪い）を示し、age_change と hybrid は**統計的に区別できない**水準で一致しました。

### 3.3 解釈

- 100 世帯規模の本実験では、hybrid は age_change と完全に同じ best_score へ収束しました。これは hybrid の前半（p_change=0.8）で age_change が選ばれて素早く局所最適に到達し、後半（p_change=0.2）で swap を 8 割選んでも局所最適から抜け出せないためと解釈できます
- H2（hybrid > age_change を含む単独戦略）は本 CI 設定では支持されません。Murata 2017 の論文と整合する観測には大規模化（フル設定 1000 世帯 + n=10）が必要です
- 一方で「hybrid が age_change より悪化することはない」点は確認できました（退行検出としての価値）

## 4. 既知の限界

- 100 世帯では age_change が早期に最適に張り付くため、hybrid の利点を観測しづらい
- p_change スケジュールは固定（0.8 → 0.2 線形）。Murata 2017 §5.2 のように複数スケジュールを比較する設計拡張は別 Issue 候補

## 5. フル設定（scale-up smoke）での結果

実施日: 2026-05-04 / scale-up smoke 設定（5 seeds × evals=2000 × 500 世帯 × 3 戦略、15 SA runs、約 8 分）。

### 5.1 best_score 一覧

| seed | age_change | age_swap | hybrid |
|---:|---:|---:|---:|
| 1 | 2260.0 | 2833.0 | 2260.0 |
| 2 | 2262.0 | 2831.0 | 2261.0 |
| 3 | 2260.0 | 2832.0 | 2260.0 |
| 4 | 2261.0 | 2833.0 | 2261.0 |
| 5 | 2260.0 | 2832.0 | 2260.0 |
| **平均** | **2260.6** | **2832.2** | **2260.4** |

### 5.2 解釈

- 500 世帯規模に拡大しても、**hybrid は age_change と統計的に区別不能**（差 ≤ 0.2）。100 世帯での観察が 5 倍規模でも維持される
- H2（hybrid > age_change を含む単独戦略）は本 scale-up smoke でも支持されず、`p_change` スケジュール（線形 0.8 → 0.2）が age_change 主導から抜け出せない構造を残しているという解釈が強化された
- age_swap の劣位は 500 世帯 × evals=2000 でも顕著で、Murata 2017 の H1b（age_swap 逆転）には evals=16000 級が必要とみられる
- 退行検出には十分機能する。`expected-full/best_scores.csv` で CI と同等の bitwise 一致を担保

## 6. 再現コマンド

```bash
make paper-results-exp02
PYTHONPATH=. uv run python paper_results/experiment-02-hybrid-strategy/run.py --full --write-expected   # scale-up smoke
```
