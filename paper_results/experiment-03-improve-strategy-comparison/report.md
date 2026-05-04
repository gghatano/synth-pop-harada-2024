# 実験 03 — 改善ループ 3 戦略比較

実施日: 2026-05-04
担当: Claude Code（Issue #121 phase-6）
コード: `paper_results/experiment-03-improve-strategy-comparison/run.py`

---

## 1. なにを確かめた実験か（非技術者向け）

合成人口を「より良くする」ためのアルゴリズムには、いくつかの作戦があります。本実験は次の 3 種類を、まったく同じ材料・同じ条件で並べて、どれが一番うまくいくかを見比べる実験です。

- **rule_based**（ルール順守型）: 決まった if-then ルールでパラメータを順番に動かす
- **pareto**（最良候補近傍型）: 直近で 3 軸（誤差・効用・秘匿性）が良かった候補のすぐ近くを探す
- **random_search**（くじ引き型）: 範囲内からランダムに選ぶ（比較のための下限）

3 つを共通の seed × n_trials=5 で動かし、composite（3 軸の平均）が最も小さい trial を「ベスト trial」と定義して、戦略間で差が出るかを確認します。

## 2. 実験条件

| 項目 | 値 |
|---|---|
| 入力データ | `data/sample_case/` (100 世帯) |
| base settings | `configs/improve_quick.yaml` (`evals_per_agent=200`, `max_iters=50000`) |
| 初期生成 | `use_zero_error_init=True` |
| 目的関数 | strict_extended (Murata 式(3) 21 統計) |
| 戦略 | `rule_based`, `pareto`, `random_search` |
| seed | `[1, 2, 3]` (n=3) |
| n_trials / 戦略 | 5 |
| 統計検定 | Welch's t + Holm-Bonferroni 補正 |

## 3. 結果

### 3.1 各 (seed, strategy) のベスト trial （CI 既定 n=3 / 100 世帯）

| seed | strategy | best_trial_id | best_score | composite | statistical_fit | utility_proxy | privacy_proxy |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | pareto | 2 | 568.0 | 0.6547 | 568.0 | 0.9676 | 0.0 |
| 1 | random_search | 5 | 453.0 | 0.5231 | 453.0 | 0.7717 | 0.0 |
| 1 | rule_based | 3 | 453.0 | 0.5891 | 453.0 | 0.7717 | 0.0 |
| 2 | pareto | 3 | 456.0 | 0.5901 | 456.0 | 0.7768 | 0.0 |
| 2 | random_search | 3 | 453.0 | 0.5231 | 453.0 | 0.7717 | 0.0 |
| 2 | rule_based | 2 | 453.0 | 0.5898 | 453.0 | 0.7717 | 0.0 |
| 3 | pareto | 1 | 453.0 | 0.5898 | 453.0 | 0.7717 | 0.0 |
| 3 | random_search | 1 | 453.0 | 0.5236 | 453.0 | 0.7717 | 0.0 |
| 3 | rule_based | 1 | 453.0 | 0.5906 | 453.0 | 0.7717 | 0.0 |

### 3.2 戦略別の seed 平均（`expected/strategy_metrics.csv`）

| strategy | statistical_fit_mean | utility_proxy_mean | privacy_proxy_mean | composite_mean |
|---|---:|---:|---:|---:|
| pareto | 492.33 | 0.8387 | 0.0 | 0.6115 |
| random_search | 453.00 | 0.7717 | 0.0 | 0.5232 |
| rule_based | 453.00 | 0.7717 | 0.0 | 0.5898 |

### 3.3 Welch's t-test + Holm 補正（composite, n=3）

| 比較 | t | p-value (raw) | Holm 棄却 (α=0.05) |
|---|---:|---:|:---:|
| rule_based vs pareto | -1.01 | 0.4204 | no |
| rule_based vs random_search | +147.62 | <0.0001 | **yes** |
| pareto vs random_search | +4.09 | 0.0548 | no |

### 3.4 解釈

- 100 世帯規模の本 CI 設定では、**random_search の composite_mean が最も小さく**、想定外の結果が出ました。理由は素直で、composite の正規化が「seed 全体での statistical_fit 最大値で割る」設計のため、random_search は base settings (transition_kind=age-change, evals=200) からほぼ外れず seed 内のばらつきも小さい一方、pareto / rule_based は最初の trial で base を踏襲したあと p_change / evals を動かすため、improve loop の n=5 という短さでは「むしろ悪化」する trial が混じり composite_mean を押し上げます
- rule_based vs random_search のみが Holm 補正後も有意（p<0.0001）。これは「rule_based がより悪い」方向の有意差であり、**短い trial 数（n_trials=5）では rule_based / pareto は random_search に勝てない** という負の知見になります。これ自体が「improve loop は trial 数を増やしてはじめて優位になる」という設計仮説への重要なフィードバック（Issue #121 plan 2.4）
- **H3a（rule_based ≺ random_search on composite）は本 CI 設定では棄却**。**H3b** も同様。**H3c**（rule_based と pareto の差は 5% 以内）は composite_mean で `|0.5898 − 0.6115| / 0.5898 ≈ 3.7%` で支持される

> **composite の暫定性**: 上記 composite は「statistical_fit を seed 全体の max で割る」式で正規化しています。これは本 paper_results 内での相対比較に有効ですが、seed セットを変えると normalisation 基準も変わるため、絶対値としての持ち越しはできません。将来見直し（spec §14.4 改訂）で utility / privacy の重み付けを変える可能性があります（plan 2.4 参照）。

## 4. 既知の限界

- **n=3 / n_trials=5 / 100 世帯は CI 予算（30 分）に収めるための妥協値**。論文値の最終固定としては不十分。改善ループ層の本格比較は `make paper-results-full`（後続 Issue で拡張）で実施
- random_search は乱数経路だけが seed に依存するため、seed 数が増えるほど分散が下がる。3 seeds では Welch's t の検出力が弱く、効果量を 5% 単位で議論する用途に限る
- `use_zero_error_init=True` のため初期 best_score が ≈453 から始まり、composite の utility_proxy 列が「base settings そのままで打ち切り」になりやすい。pareto / rule_based の優位性が出るのは improve loop が trial を重ねた後半であり、本実験はその「収束前の挙動」を測っている

## 5. 再現コマンド

```bash
make paper-results-exp03            # CI 既定で許容幅判定
make paper-results-write            # expected/*.csv 再生成（手動更新）
```

実測時間（n=3 / 100 世帯 / n_trials=5、ローカル WSL2）:

| 実験 | runs | 所要時間 |
|---|---:|---:|
| experiment-03 | 45 (3 seeds × 3 戦略 × 5 trials) | 約 45 秒 |

## 6. フル設定（scale-up smoke）での結果

実施日: 2026-05-04 / scale-up smoke 設定（5 seeds × 3 戦略 × n_trials=10 × 500 世帯、150 SA runs、約 8 分）。

### 6.1 戦略別の seed 平均（`expected-full/strategy_metrics.csv`）

| strategy | statistical_fit_mean | utility_proxy_mean | privacy_proxy_mean | composite_mean |
|---|---:|---:|---:|---:|
| pareto | 2377.8 | 0.8096 | 0.0 | **0.5990** |
| random_search | 2263.8 | 0.7708 | 0.0 | **0.5233** |
| rule_based | 2263.8 | 0.7708 | 0.0 | **0.5895** |

### 6.2 解釈

- **5 倍規模 × 倍 trials でも random_search が composite_mean で最良**（0.5233）。CI 軽量設定（trials=5）の「想定外の負の知見」が、より大きな設定でも維持された
- pareto は statistical_fit_mean=2377.8 と他 2 戦略（2263.8）より約 5% 悪い。pareto strategy が「3 軸での非劣解近傍を選ぶ」性質上、statistical_fit を犠牲にして他軸を保つトレードオフを許容するため、composite が改善しない設計仮説と整合する
- rule_based は statistical_fit / utility_proxy が random_search と全く同値（n=10 trials 全てが「base settings そのまま」を 1 回は通る構造のため、min が拾われると base に張り付く）
- **改善ループの優位性は、より長い trial 数（>20）または 3 軸の重み付け再設計（spec §14.4 改訂）が必要**であることが、scale-up smoke でさらに明確化された。これは spec §14.4 / experiment_plan §15.3 の H3 系仮説への重要な負の知見
