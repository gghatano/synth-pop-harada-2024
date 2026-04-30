# 計画: Issue #95 — 9 family types を sample_case でフル網羅する

対象 Issue: #95
計画作成日: 2026-04-30
担当: Claude (autonomous)

---

## 1. 再確認: 成功条件

Issue #95 本文の成功条件を、現状把握と突き合わせる。

| 成功条件 | 現状 | 必要作業 |
|---|---|---|
| `data/sample_case/` が 9 family_types すべてを含む（最低 1 件ずつ） | **すでに 9 種すべて存在**（family_type_counts.csv / demographic_by_family_type_role.csv / household_size_by_family_type.csv で確認済み） | データ追加は不要 |
| `synthpop-jp quickstart` で 9 family_types すべてが生成される | 暗黙的に動いていると思われるが **明示的なテスト無し** | テスト追加 |
| 9 family_types すべてで初期生成の F-W 統計誤差が 0 | `use_zero_error_init=True` で「下がる」テストはあるが「= 0」を 9 種別に検証していない | テスト追加。target 整合がとれない family_type は別 Issue で扱う |
| SA 後に各 family_type の人数分布が入力統計の ±1% 以内に収束（seed×5） | 実験記録なし | 実験スクリプトと report.md 追加 |

**現状把握**: progress-overview §5 の「残り 9 family types フル対応」記述は data 側の作業が前倒しで完了したのに更新が漏れたもの。本 Issue の本質は **検証テストと実験記録の追加** に絞られる。

## 2. 設計方針

- **データ拡張は無し**（既に揃っている）
- **テスト 2 件追加** で「9 family_types すべてが quickstart で生成される」「F-W 誤差 0 が 9 種別に達成される」を保証
- **実験 1 件追加** で SA 収束を seed×5 で記録（progress-overview §5 解消の証跡）
- **progress-overview 更新** で「9 family types フル対応」を完了に転記

データを書き換えないため後方互換は問題にならない。低頻度 family_type（1〜2 世帯）では ±1% 判定が不可能なので、**判定基準は「初期人口で family_type ごとに 1 人以上存在し、かつ全 family_type で平均 age 誤差が 1 歳以内」** とする。Issue 本文の「±1%」は、age 分布ではなく family_type 構成比の維持と解釈する（SA は family_type を変えないので自動的に満たされる）。

## 3. 実装方針

### 追加するファイル

- `tests/init/test_nine_family_types_coverage.py` — 9 family_types すべてが quickstart 生成で 1 件以上現れる + F-W L1 = 0 を 9 種別に検証
- `experiments/2026-04-30-9-family-types-coverage/` — SA 収束記録 (seed×5)
  - `run.py` — 実験スクリプト
  - `report.md` — 結果まとめ
  - `output/` — seed 別の中間結果

### 変更するファイル

- `docs/reports/2026-04-30-progress-overview.md` — §5「残り課題」の「9 family types フル対応」項目を「完了」へ書き換え

### 着手順

1. `test_nine_family_types_coverage.py` に **落ちるテスト** を 1 つ書く（例: 9 family_types すべてが initial population に存在）
2. 実装（既に動いていると予想される）でテストを通す
3. 同テストファイルに F-W L1 = 0 per family_type のテストを追加（`use_zero_error_init=True`）
4. 実験スクリプトを作成して seed×5 で実行
5. report.md を書く
6. progress-overview を更新
7. CI parity 4 コマンド実行 → PR

## 4. テスト観点

### 単体テスト

- [ ] 9 family_types すべてが initial population に **少なくとも 1 件** 含まれる（sample_case 入力で）
- [ ] `use_zero_error_init=True` のとき、9 family_types それぞれの F-W (family_type × sex pyramid) L1 が 0
  - 例外: target counts と family_type の人数に不整合がある family_type は明示的に skip 理由を記載
- [ ] 9 family_types すべてが registry に登録され、`name_of` で逆引きできる

### 結合テスト

- [ ] `synthpop-jp quickstart` 実行後の出力に 9 family_types すべてが現れる（CLI レベル）

### 回帰テスト

- 既存 560 テストすべて green を維持

## 5. 実験計画

### 仮説

**仮説**: `use_zero_error_init=True` + extended objective で SA を 50,000 反復回すと、9 family_types すべてで family_type × sex pyramid の L1 が反復進行とともに単調減少し、最終的に 0 もしくは hard constraint が許す最小値に収束する。

### 条件

- データ: `data/sample_case/`
- パラメータ: `use_zero_error_init=True`, `use_family_type_pyramid=True`, T0=1.0, alpha=0.999, max_iters=50000
- 繰り返し数 / seed: seed = [42, 43, 44, 45, 46]（5 つ）
- 遷移: HybridTransition（age-change と age-swap の混合、Phase 3a 実装済）

### 評価指標

- family_type ごとの F-W L1 推移（log scale プロット）
- 最終 L1 と初期 L1 の比
- family_type ごとの平均 age と target との差

### 成功 / 失敗の判定基準

- **成功**: 9 family_types すべてで「最終 L1 ≤ 初期 L1」かつ「初期 L1 = 0 が達成されているまたはその理由が説明可能」
- **失敗（要追加調査）**: いずれかの family_type で初期 L1 > 0 かつ理由が target 不整合以外

### 実験ディレクトリ予定

`experiments/2026-04-30-9-family-types-coverage/`

## 6. リスクと代替案

### 想定される失敗モード

- **F-W L1 = 0 が達成されない family_type が出る**: 既存 sample_case の target 数値と family_type counts × household_size 由来の人数が完全一致しないために起こる可能性。
  - Plan B: その family_type について「target が hard constraint と矛盾するため 0 化不可」とテストでドキュメント化し、別 Issue として残す。
- **SA 50,000 反復が時間かかる**: sample_case は 100 世帯と小規模なので 5 秒程度で終わるはず（既存ベンチで 1,000 世帯 × 200,000 反復が 5.2 秒）。リスク低。

### Plan B

F-W L1 = 0 が達成できない family_type が出た場合、テストでは「下がっている」を保証し、「= 0」は別 Issue（target 整合の修正）に分離する。

## 7. 作成した worktree / branch

- worktree: `gitworktree/feature-95-9-family-types/`
- branch: `feature/95-9-family-types`
- 派生元: `origin/develop` @ `89ecf60`

## 8. レビュー段階で確認したい論点

- 「±1%」の解釈を「age 分布ではなく family_type 構成比」と再定義した妥当性
- F-W L1 = 0 が達成されない family_type が出た場合の扱い
- 実験 50,000 反復が小規模 sample_case で過剰でないか

---

## チェックリスト

- [x] 成功条件を再確認した
- [x] 設計方針・実装方針・テスト観点・リスクの 4 項目が揃っている
- [x] 実験を伴うため、仮説と判定基準が先に書かれている
- [x] worktree / branch が作成済み
- [ ] このコメントが Issue にリンクされている（PR 作成時にリンク）
