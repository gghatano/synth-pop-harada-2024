# 計画: Issue #96 — broad utility 評価器

対象 Issue: #96
計画作成日: 2026-04-30
担当: Claude (autonomous)

---

## 1. 再確認: 成功条件

| 成功条件 | 担保方法 |
|---|---|
| `BroadUtilityEvaluator` が独立クラスとして実装される | `src/synthpop_jp/evaluate/utility/broad.py` |
| 単変量 TV / L1 per attribute、属性ペア joint TV、相関 Frobenius 差の 3 指標が `metrics.json` に出力される | `evaluate(synthetic, holdout)` の戻り値キーで保証 |
| `synthpop-jp evaluate` から自動呼び出しされる | CLI に `--real-persons-csv` がある場合に実行 |
| 既知の小データで数値計算が手計算と一致するユニットテスト | `tests/evaluate/test_broad_utility.py` |
| Table 13 形式 `report.md` に該当セクションが追記される | `src/synthpop_jp/reports/markdown.py` 拡張 |

## 2. 設計方針

### 2.1 評価器の構造

CAPEvaluator と同様、**`evaluate(synthetic, holdout)` シグネチャ** を採用する（broad utility は real reference を要するため）。`Evaluator` Protocol（`evaluate(pop)`）には適合しないが、CAPEvaluator が同じ理由で外れているのと同型の判断。`PrivacyMetric` Protocol も借用しない（layer が異なる）。

将来 `UtilityMetric` Protocol を追加する場合は別 Issue で扱う。本 PR は **クラス単体で成立する MVP** に絞る。

### 2.2 計算する指標

`docs/spec/spec.md` §13.2 / `docs/spec/metrics.md` §3 に基づき、以下を MVP として実装する。

| カテゴリ | 指標 | 出力キー |
|---|---|---|
| 単変量 | TV (Total Variation distance) | `broad_utility.tv.<attr>` |
| 単変量 | L1 (= 2*TV) | `broad_utility.l1.<attr>` |
| ペア | joint TV per pair | `broad_utility.pair_tv.<a>__<b>` |
| 相関 | Frobenius diff（混合型相関行列） | `broad_utility.correlation_frobenius_diff` |
| 相関 | max-abs diff | `broad_utility.correlation_max_abs_diff` |
| 集約 | sum_pair_tv（ペア TV の総和） | `broad_utility.sum_pair_tv` |

対象属性は `("age", "sex", "role", "family_type")` の 4 つ（household_id は粒度が細か過ぎ、analysis 対象外）。

### 2.3 混合型相関の実装（dython 準拠）

外部依存 `dython` を **追加しない**（テストの数値一致は手計算 fixture で達成）。

| 組合せ | 計算 |
|---|---|
| age × age（同一） | 1.0（自己相関） |
| age × {sex, role, family_type} | Correlation Ratio（連続→カテゴリ） |
| {sex, role, family_type} 内ペア | Cramér's V（カテゴリ→カテゴリ、補正なし） |

Theil's U / Pearson は MVP では不採用（age はこのデータでは唯一の連続変数のため Pearson が出る組合せが無い）。Theil's U は asymmetric なため対称行列にならない → Frobenius 差を素直に取れない、対象外。

実装は `numpy` + `scipy.stats.chi2_contingency` で完結。

## 3. 実装方針

### 追加するファイル

- `src/synthpop_jp/evaluate/utility/__init__.py` — 空ファイル
- `src/synthpop_jp/evaluate/utility/broad.py` — `BroadUtilityEvaluator` 実装
- `tests/evaluate/test_broad_utility.py` — ユニットテスト（手計算 fixture）

### 変更するファイル

- `src/synthpop_jp/cli.py` — `evaluate` 関数に `BroadUtilityEvaluator` を組み込む（`--real-persons-csv` 有のとき呼ぶ）
- `src/synthpop_jp/reports/markdown.py` — Broad utility セクションを report.md に追加（既存の Table 13 セクション末尾に追記）
- `tests/cli/test_evaluate.py` — CLI 経由で broad_utility キーが出力されるテスト追加
- `tests/reports/test_markdown.py` — broad utility セクション出力テスト追加

### 着手順（小さい TDD サイクル）

1. **Cycle 1**: 単変量 TV / L1 のテストを書く（家族構成の小サンプルで手計算）→ 実装
2. **Cycle 2**: ペア joint TV のテスト → 実装
3. **Cycle 3**: Cramér's V / Correlation Ratio の単体テスト → 実装
4. **Cycle 4**: correlation_frobenius_diff / max_abs_diff のテスト → 実装
5. **Cycle 5**: CLI 統合テスト → CLI 修正
6. **Cycle 6**: report.md セクションテスト → markdown 修正

## 4. テスト観点

### 単体テスト

- [ ] `_tv(p, q)` が手計算と一致（既知配列）
- [ ] `_univariate_tv(synth, real, attr)` が age・sex・role・family_type で動く
- [ ] `_pair_joint_tv(synth, real, a, b)` が手計算と一致
- [ ] `_cramers_v(x, y)` が独立性で 0、完全従属で 1
- [ ] `_correlation_ratio(num_x, cat_y)` がグループ平均一定で 0
- [ ] `BroadUtilityEvaluator.evaluate(synth, real)` が期待キーをすべて含む
- [ ] 同一データを synth/real に渡すと TV=0、frobenius=0

### 結合テスト

- [ ] CLI 経由で `--real-persons-csv` を渡したとき `metrics.json` に `broad_utility.*` キーが含まれる
- [ ] `--real-persons-csv` 未指定なら broad_utility は出力されない

### 回帰テスト

- 既存 605 テストが grenshouse green を維持

## 5. 実験計画

該当なし（評価器自体の動作確認は単体テストで十分。実データでの数値感はフォローアップ Issue で）。

## 6. リスクと代替案

### 想定される失敗モード

- **dython と数値が完全一致しない**: Cramér's V には bias correction が複数バージョンある。本 PR は **bias correction 無しの素朴な V**（Bergsma 補正なし）で固定し、テストでも同じ式の手計算を期待値とする。dython の選択肢との微小差は別 Issue。
- **household_id を分析に含めるべきか**: 含めない（unique 値が大きすぎてカテゴリ相関が無意味）。Issue #96 のスコープ外として明記。

### Plan B

dython と完全一致が要求された場合は別 Issue として `dython` を dev-dependency 化し、参照値テストを追加する。

## 7. 作成した worktree / branch

- worktree: `gitworktree/feature-96-broad-utility/`
- branch: `feature/96-broad-utility`
- 派生元: `origin/develop` @ `9d188c5`（#95 マージ後）

## 8. レビュー段階で確認したい論点

- `dython` を dev-dep に追加せず手計算 fixture でテストする判断
- `Theil's U` を MVP 不採用とした判断（asymmetric のため Frobenius と整合しない）
- `household_id` を broad utility 対象外とした判断
- CLI の `--real-persons-csv` 条件分岐方針

---

## チェックリスト

- [x] 成功条件を再確認した
- [x] 設計方針・実装方針・テスト観点・リスクの 4 項目が揃っている
- [x] 実験は伴わない（該当なし）
- [x] worktree / branch が作成済み
- [ ] PR 本文から Issue にリンク
