# 計画: Issue #97 — narrow utility 評価器

対象 Issue: #97
計画作成日: 2026-04-30
担当: Claude (autonomous)

---

## 1. 再確認: 成功条件

| 成功条件 | 担保方法 |
|---|---|
| 3 タスクの TSTR/TRTS が実装される | `NarrowUtilityEvaluator.evaluate(synth, real)` |
| 評価結果が `metrics.json` に書き出される | CLI に組み込み |
| baseline モデル選択が固定で再現可能 | sklearn 既定パラメータ + seed 固定 |
| hold-out split が seed 固定で再現可能 | `train_test_split(..., random_state=seed)` |
| sanity check: TSTR/TRTS > random baseline | sample_case で test 追加 |

## 2. 設計方針

### 2.1 タスク定義（spec §13.2 / metrics.md §4 準拠、事後変更禁止）

| タスク | レベル | 入力 | 出力 | 指標 | モデル |
|---|---|---|---|---|---|
| A: family_type 分類 | per-person | age, sex, household_size | family_type | macro-F1 | LogisticRegression |
| B: 世帯人数回帰 | per-household | family_type, n_children | household_size | RMSE | LinearRegression |
| C: 役割予測 | per-person | age, sex, family_type | role | macro-F1 | LogisticRegression |

**「世帯内 role 分布」は household 単位の特徴量で、個人単位タスクと整合しない。** spec §13.2 の元定義を簡素化して `household_size` を per-person broadcast 特徴量として使う（Issue #97 計画 §2.1 にて記録、別 Issue で再定義可能）。

### 2.2 評価フロー

```
synthetic (n=N_syn)            real (n=N_real)
       │                              │
       │  task A: 全件で train        │  task A: 全件で test
       └──────────────────────────────┘  → TSTR  
       
       real (n=N_real)               synthetic (n=N_syn)
       │  task A: 全件で train       │  task A: 全件で test
       └──────────────────────────────┘  → TRTS
```

**hold-out split しない**: synth と real は別物として扱う。TSTR は full synth で学習・full real で評価、TRTS は逆。これは spec §13.2 の標準解釈。

### 2.3 評価器 API

```python
class NarrowUtilityEvaluator:
    name = "narrow_utility"
    
    def __init__(self, seed: int = 42):
        self.seed = seed
    
    def evaluate(self, synthetic: PopulationArrays, holdout: PopulationArrays) -> dict[str, float]:
        # → {
        #   "narrow_utility.task_a.tstr_macro_f1": ...,
        #   "narrow_utility.task_a.trts_macro_f1": ...,
        #   "narrow_utility.task_b.tstr_rmse": ...,
        #   "narrow_utility.task_b.trts_rmse": ...,
        #   "narrow_utility.task_c.tstr_macro_f1": ...,
        #   "narrow_utility.task_c.trts_macro_f1": ...,
        # }
```

## 3. 実装方針

### 追加するファイル

- `src/synthpop_jp/evaluate/utility/narrow.py` — `NarrowUtilityEvaluator`
- `tests/evaluate/test_narrow_utility.py` — ユニットテスト

### 変更するファイル

- `src/synthpop_jp/cli.py`: `evaluate` で `--real-persons-csv` 指定時に呼び出し
- `src/synthpop_jp/reports/markdown.py`: §3 broad utility の後に §3.5 narrow utility セクション追加（or §3 内のサブセクション）
- `tests/cli/test_evaluate.py`: narrow_utility キーの CLI 統合テスト
- `tests/reports/test_markdown.py`: narrow utility セクションテスト

### 着手順（小さい TDD サイクル）

1. **Cycle 1**: Task A（family_type 分類）の TSTR テスト → 実装
2. **Cycle 2**: Task B（household_size 回帰）の TSTR テスト → 実装
3. **Cycle 3**: Task C（role 予測）の TSTR テスト → 実装
4. **Cycle 4**: TRTS（3 タスク）テスト → 実装（対称性で実装は薄い）
5. **Cycle 5**: CLI / report.md 統合

## 4. テスト観点

### 単体テスト

- [ ] Task A: synth=real で TSTR macro-F1 ≥ 0.5（trivial baseline は random）
- [ ] Task B: synth=real で TSTR RMSE が finite かつ非負
- [ ] Task C: synth=real で TSTR macro-F1 ≥ 0.5
- [ ] Evaluator name == "narrow_utility"
- [ ] 期待キー（6 個）がすべて含まれる
- [ ] empty 入力で 0 / NaN にならない（中立値で埋める）
- [ ] seed 固定で 2 回呼んで bitwise 一致

### 結合テスト

- [ ] CLI で `--real-persons-csv` 指定時に narrow_utility キー追記
- [ ] 未指定時はキー無し

### 回帰テスト

既存 627 テスト green を維持

## 5. 実験計画

該当なし（評価器の動作は単体テストで担保）。

## 6. リスクと代替案

### 失敗モード

- **sklearn のバージョン依存で再現性が崩れる**: lockfile 固定で対処（既存方針）。テストは数値範囲で許容
- **role 値が test set にしか無いと macro-F1 が NaN**: train/test 両方に同じ unique を保証する fixture を組む
- **household-level 特徴量の per-person broadcast の意味曖昧**: 計画で明記、spec 改訂は別 Issue

### Plan B

3 タスクすべて成立しない場合は、最低 1 タスク（Task A）のみで PR を出し、残りは別 Issue へ分離する。

## 7. 作成した worktree / branch

- worktree: `gitworktree/feature-97-narrow-utility/`
- branch: `feature/97-narrow-utility`
- 派生元: `origin/develop` @ `9d188c5`

## 8. レビュー段階で確認したい論点

- 「世帯内 role 分布」の解釈を `household_size` で簡素化した妥当性
- TSTR/TRTS で hold-out split を **しない** 判断（synth と real を独立サンプルとみなす）
- macro-F1 の `zero_division=0.0` 設定（クラス欠損時の挙動）

---

## チェックリスト

- [x] 成功条件を再確認した
- [x] 設計方針・実装方針・テスト観点・リスクの 4 項目が揃っている
- [x] 実験は伴わない
- [x] worktree / branch が作成済み
- [ ] PR 本文から Issue にリンク
