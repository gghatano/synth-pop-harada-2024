# Experiment Report Format（比較レポートと metrics.json の仕様）

**ステータス: 骨子（Phase 3b で肉付け）**

本ドキュメントは `synthpop-jp compare` サブコマンドの入出力仕様、および全 run が共通で出力する `metrics.json` スキーマを固定する。`docs/spec/spec.md` §13〜§15 から本書に委譲されている。

## 1. `synthpop-jp compare` の入力 config 形式

`configs/compare_*.yaml` の形式を Phase 3b で確定する。想定する要素:

- `base_config`: 基準となる `configs/base.yaml`
- `variants`: 比較対象の上書きリスト（例: `transition: age_change` と `transition: age_swap`）
- `seeds`: seed 群（n=10〜30）
- `bootstrap_iterations`: 既定 2,000
- `significance_test`: `welch_t` | `wilcoxon_signed_rank`
- `multiple_comparison_correction`: `holm` | `none`

**Phase 3b で確定。**

## 2. Seed 群実行ポリシー

- 各条件で seed n=10〜30 の多試行
- seed は `SeedSequence.spawn(n)` で根 seed から決定論的に生成（`spec.md` §18.1）
- 並列実行は `pytest-xdist` ではなく `joblib` / `concurrent.futures` を使う
- 並列でも bitwise 再現を保つ（各 trial は独立 seed）

**Phase 3b で実装。**

## 3. Bootstrap CI 算出規約

- 方法: **percentile bootstrap**
- 反復回数: 既定 2,000
- 信頼水準: 95%（両側）
- `numpy.random.Generator.choice` を resample に使う（scipy ではなく）
- CI が生の値とともに `metrics.json` に記録される

## 4. 有意差判定

- **独立群の主比較**: Welch's t test + Holm 補正
- **対応群の比較**（同 seed で条件違い）: Wilcoxon signed-rank test
- **Effect size**: Cliff's δ を必ず併記
- 多重比較は Holm（Bonferroni より検出力が高い）

## 5. 出力 `report.md` の固定セクション構造

Phase 3b で次の順で生成する:

1. Run メタデータ（git_sha、uv.lock hash、numpy_version、実行時刻）
2. 入力 config の抜粋
3. 統計整合性（21 統計ブレークダウン、Table 13 形式）
4. Broad utility
5. Narrow utility（TSTR / TRTS）
6. Privacy 3 層（proxy / CAP / MIA）
7. Rare cell 監視
8. 検定結果（Welch's t / Wilcoxon / Holm 補正後 p 値 / Cliff's δ）
9. **出典とライセンス注記**（`writers.py` が自動埋込、e-Stat 利用時は統計法 §44 出典表示）
10. 再現手順（`uvx synthpop-jp compare --experiment ...`）

**Phase 3b で `writers.py` に実装。**

## 6. `metrics.json` スキーマ

最小フィールド:

```json
{
  "run_id": "string",
  "git_sha": "string",
  "uv_lock_hash": "string",
  "numpy_version": "string",
  "python_version": "string",
  "seed": 42,
  "timestamp_utc": "2026-04-23T12:00:00Z",
  "config": { "...": "config.yaml の全内容を埋め込み" },
  "objective": {
    "mode": "paper | research_extended",
    "best_score_paper": 123.4,
    "best_score_research": 45.6
  },
  "aggregate_metrics": {
    "per_statistic_l1": { "father_child_gap": 0.12, "...": "21 統計ブレークダウン" },
    "pyramid_1yr_tv": 0.03,
    "pyramid_5yr_tv": 0.02
  },
  "broad_utility": {
    "univariate_l1": 0.01,
    "correlation_frobenius_diff": 0.05
  },
  "narrow_utility": {
    "task_a_tstr_macro_f1": 0.85,
    "task_a_trts_macro_f1": 0.83,
    "task_b_tstr_rmse": 1.2,
    "task_c_tstr_macro_f1": 0.78
  },
  "privacy": {
    "proxy": { "dcr_p05": 0.08, "nndr_p05": 0.45, "ard": 0.12 },
    "cap": { "generalized": 0.31, "tcap": 0.28 },
    "mia": { "tapas_auc": null, "domias_auc": null }
  },
  "rare_cell": {
    "ratio_cell_lt_5": 0.04,
    "unique_ratio": 0.01
  }
}
```

**JSON Schema を `schemas/metrics.schema.json` として Phase 3b でコミット。**

## 7. 履歴

- 2026-04-23: v0.0.1 骨子作成（Phase 0）
