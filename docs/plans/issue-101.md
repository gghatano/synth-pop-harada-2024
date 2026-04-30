# 計画: Issue #101 — report.md ジェネレータに出典・ライセンス自動埋込

対象 Issue: #101
計画作成日: 2026-04-30

---

## 1. 再確認: 成功条件

| 成功条件 | 担保方法 |
|---|---|
| `report.md` に「出典」「ライセンス」セクションが自動生成される | `_render_citations` / `_render_licenses` |
| 各 Evaluator から出典を取得できる | データ駆動の citation lookup table |
| e-Stat 利用時のライセンス注記が自動挿入される | `provenance.json` の有無 or input_dir 名で検出 |
| 既存 4 評価器で出典が埋まる | aggregate, rare_cell, cap, broad/narrow utility |
| 既存 report.md の後方互換 | 既存テスト green |

## 2. 設計方針

**Evaluator クラスに `citation` 属性を追加する案** ではなく、**`markdown.py` 側で metrics キーから出典をデータ駆動で引く案** を採用する。理由:

- Evaluator 数は限定的（aggregate / rare_cell / cap / broad_utility / narrow_utility / 将来の DCR/NNDR/ARD/MIA）
- データ駆動の dict は変更が 1 ファイルで完結し、過去の評価結果（古い metrics.json）にも遡及できる
- Protocol を破壊的に変更しない

### 2.1 出典 lookup table

```python
_CITATIONS: dict[str, str] = {
    "aggregate.l1.": "Murata 2017 §11.4 式(1)/(3): f(A) = Σ_s Σ_j |c_{sj}(A) - R_{sj}|",
    "rare_cell.": "Murata 2017 §11.6 / Priv 指摘 4: rare family_type cell の k-anonymity 観点",
    "cap.": "Taub et al. (2018) 'Differential Correct Attribution Probability'",
    "broad_utility.": "Harada 2024 §5.1 broad utility / dython.associations 準拠 (Cramér's V, Correlation Ratio)",
    "narrow_utility.": "Harada 2024 §5.1 narrow utility (TSTR/TRTS) / Esteban et al. (2017)",
    "mia.": "Houssiau et al. (2022) TAPAS / van Breugel et al. (2023) DOMIAS",
}
```

### 2.2 ライセンス検出

`render_metrics_table13` に新引数 `provenance: dict | None = None` を追加。`provenance` に `data_source: "e-stat"` が含まれれば e-Stat の出典表示を自動追加。`None` なら sample_case 用の dummy ライセンス文を出す。

## 3. 実装方針

### 追加するファイル

無し（既存 `markdown.py` を拡張）

### 変更するファイル

- `src/synthpop_jp/reports/markdown.py`: `_CITATIONS`, `_render_citations`, `_render_licenses` 追加、`render_metrics_table13` のシグネチャ拡張
- `src/synthpop_jp/cli.py`: `evaluate` で provenance を読み込んで渡す
- `tests/reports/test_markdown.py`: 出典セクション・ライセンスセクションのテスト追加

### 着手順

1. **Cycle 1**: `_render_citations` の RED テスト → 実装
2. **Cycle 2**: `_render_licenses` の RED テスト → 実装
3. **Cycle 3**: CLI 統合（provenance 読み込みは sample_case で `None` のまま）
4. **Cycle 4**: 後方互換テスト（provenance 引数省略時に既存挙動）

## 4. テスト観点

- [ ] aggregate.l1.* キーがあるとき Murata 2017 出典が含まれる
- [ ] cap.* キーがあるとき Taub 2018 出典が含まれる
- [ ] broad_utility.* キーがあるとき Harada 2024 / dython 出典が含まれる
- [ ] narrow_utility.* キーがあるとき Harada 2024 / Esteban 出典が含まれる
- [ ] provenance=None でデフォルトライセンス文が出る
- [ ] provenance={"data_source": "e-stat"} で e-Stat 出典が出る
- [ ] 既存 render_metrics_table13 呼び出し（provenance なし）が壊れない

## 5. リスクと代替案

### 失敗モード

- **出典文が冗長**: 短文に絞り、詳細は spec へのリンクで誘導
- **e-Stat 検出ロジックの誤検出**: `data_source` 明示指定のみに限定（heuristic を使わない）

### Plan B

Evaluator Protocol に `citation` を追加する案。本実装は data-driven で MVP、Protocol 拡張は別 Issue。

## 6. worktree

- worktree: `gitworktree/feature-101-citation-embed/`
- branch: `feature/101-citation-embed`
- 派生元: `origin/develop` @ `7cff646`
