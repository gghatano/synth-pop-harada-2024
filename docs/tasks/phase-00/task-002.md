# task-002: 契約・仕様ドキュメントの骨子先置き

## 目的

spec.md から委譲される各契約・仕様ドキュメントの**骨子**（章立てと空セクション）を先置きし、後続 Phase で肉付けしやすい土台を作る。本タスクでは中身の確定はしない（Phase 1〜3 で埋める）。

## 前提・依存

- task-001 で spec.md からの委譲先として本ドキュメント群が参照されている前提。
- 骨子の段階では「未定」「Phase N で埋める」と明記してよい。

## 成果物

以下のファイルを新規作成（骨子のみ）:

### a. `docs/spec/data_contract.md`（Py 指摘2）

章立て:
1. 対象範囲と責務
2. ファイル別スキーマ（§7.1 全 CSV を列・型・単位・欠損規則で再記述）
3. 半開区間文字列と diff_min/diff_max の規約
4. `couple_diff = husband_age - wife_age` の符号規則
5. `family_type` ↔ `family_type_group` マッピング（yaml 配布先を明記）
6. pydantic v2 `TypeAdapter` エラーメッセージ規約
7. 変更履歴（SemVer）

### b. `docs/spec/metrics.md`（Py 指摘12 / Priv 指摘2,3,5,6）

章立て:
1. 距離の基本方針（Gower 距離、連続は [0,1] 正規化、カテゴリはマッチ/非マッチ）
2. 統計整合性指標（L1 primary, L2, χ², TV 5歳/1歳刻み）
3. Broad utility 指標（mixed-type 相関: Theil's U / Cramér's V / Correlation Ratio、Frobenius 差）
4. Narrow utility 指標（TSTR / TRTS、固定 3 タスク、macro-F1 / RMSE）
5. Privacy 指標 3 層:
   - (a) DCR / NNDR / ARD（proxy、Gower）
   - (b) Generalized CAP / TCAP（MVP 必須、式とアルゴリズム）
   - (c) TAPAS / DOMIAS（Phase 5）
6. Rare cell 監視（family_type × age で cell<5 の割合、unique 率）

### c. `docs/spec/experiment_report_format.md`（Py 指摘8）

章立て:
1. `synthpop-jp compare` の入力 config 形式
2. seed 群実行ポリシー（n=10〜30）
3. bootstrap CI 算出規約
4. 有意差判定（Welch's t + Holm、Wilcoxon signed-rank、Cliff's δ）
5. 出力 `report.md` の固定セクション構造
6. `metrics.json` スキーマ

### d. `docs/experiment_plan.md`（Priv 指摘8 / タスクE）

章立て（実験事前登録形式）:
1. 実験 1（§15.1）: 仮説 / 指標 / 統計検定 / サンプルサイズ / 停止条件
2. 実験 2（§15.2）: 同上
3. 実験 3（§15.3）: rule_based vs Pareto の主要比較
4. 実験 4（§15.4）: 複数候補のばらつき
5. `shadow seed` 群の運用
6. Pre-registration 凍結手順（git tag + SHA 記録）

### e. `docs/assumptions.md`（Priv S5/S6 / OSS 指摘2）

章立て:
1. 評価用 "real" 個票 protocol（semi-synthetic 設定）
2. 利用候補データセット（ACS PUMS / IPUMS / e-Stat 公開ミクロデータの利用規約）
3. Hold-out 手順と cell size 制限
4. IRB / data use agreement 要件（該当時）
5. 統計法 §44・e-Stat 利用規約（出典表記義務）
6. 倫理記録テンプレ（どのデータセット・版・取得者・取得日）

## 受け入れ基準

- 上記 5 ファイルが `docs/spec/` または `docs/` 直下に新規存在する。
- 各ファイルは章立てと「Phase N で埋める」注記のみで可。
- spec.md（task-001）からの内部リンクが 5 ファイル全てに通っていること（相対パスでリンク確認）。

## 推定規模

S（2〜3 時間）。骨子のみ。

## 参照

- `docs/reviews/action-plan.md` §2B
- `docs/reviews/review-privacy.md` 追加タスク A〜H
- `docs/reviews/review-python.md` 指摘 2, 8, 12
