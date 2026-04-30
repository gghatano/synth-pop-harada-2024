# 2026-04-30 進捗オーバービュー — Phase 1〜3 の到達点と実験結果

このドキュメントは、リポジトリを初めて触る人や、しばらく離れていた人が **「いま何が動いて、何が分かっていて、次に何をすれば良いか」を 1 ファイルで把握できる** ことを目的としています。

専門用語が出てくる箇所には一言の補足を添えています。詳細は各セクションのリンク先（spec / 個別レポート / 実験記録）に逃がしてあります。

- 対象 develop SHA: `60f00d9`（PR #50 merged 直後）
- 本体テスト: 560 passed / 10 skipped
- 関連レポート: `docs/reports/2026-04-29-phase3-extended-summary.md`、`docs/reports/2026-04-29-phase3-handoff.md`、`docs/reports/phase-02-benchmarks.md`

---

## 1. 非技術者向け要約

合成人口（公開されている統計だけを材料に、人工的に作った世帯と個人のデータ）を作る道具を、Python で作っています。

これまでに次の 3 つが揃いました。

- **作る**: 統計に合うように、世帯と個人の合成データをコマンド 1 つで生成できる
- **整える**: 焼きなまし法（後述）と呼ばれる仕組みで、生成したデータを少しずつ統計に近づけられる
- **評価する**: 出来上がった合成データが「統計にどれくらい一致しているか」「個人を特定されるリスクがどれくらいか」を数値で測れる

これらをすべて、コマンドラインから一連の流れとして使えます。性能面でも目標を上回っており（後述、1,000 世帯規模なら数秒で生成）、研究プロトタイプとしては実用段階に入りました。

残っているのは、より多くの統計に対応すること（家族類型を 9 種類フル対応に増やす、目的関数を 21 統計まで広げる）と、e-Stat（政府統計の総合窓口）の実データを直接読み込む配管の整備です。

---

## 2. 現在地（一目で）

### 何ができるか

| 区分 | コマンド | 役割 |
|---|---|---|
| 生成 | `synthpop-jp quickstart` | 同梱ダミーデータから合成世帯・個人を 10 秒以内に生成 |
| 生成 | `synthpop-jp generate --config foo.yaml` | 任意の設定で合成人口を生成（SA 含む） |
| 検証 | `synthpop-jp validate-config configs/base.yaml` | 設定 YAML の妥当性チェック |
| 評価 | `synthpop-jp evaluate <persons.csv>` | 統計誤差・rare cell・CAP/TCAP を `metrics.json` に書き出し |
| 比較 | `synthpop-jp compare <config1> <config2> --seeds 10` | 複数 config × n seed で SA を回し、統計検定（Welch / Wilcoxon + Holm 補正）と bootstrap CI 付きの比較レポートを出す |

使い方の詳細は [`docs/guides/how-it-works.md`](../guides/how-it-works.md) を参照してください。

### 主要な数値

- **生成性能**: 1,000 世帯 × 200,000 反復 SA が median 5.2 秒（目標 30 秒に対し 5.8 倍余裕）
- **メモリ消費**: 100,000 世帯規模でも SA peak RSS は 358MB（25.8GB 物理 RAM の 1.4%）
- **テスト**: 本体 560 passed / 10 skipped、CI smoke ベンチも組み込み済み
- **評価器**: aggregate L1（5 統計＋extended で +10）/ rare cell / CAP/TCAP の 3 種が同時実行可能

### コードの分離

3 つの軸が独立に拡張できる構造になっています（spec §11〜§13、Protocol で分離）。

- **作る** （遷移 / Transition）: `src/synthpop_jp/optimize/transitions.py`
- **整える** （目的関数 / Objective）: `src/synthpop_jp/optimize/objective.py`
- **評価する** （Evaluator / PrivacyMetric）: `src/synthpop_jp/evaluate/`

新しい遷移や評価指標を足すときは、それぞれ独立に PR 1 本で完結できます。

---

## 3. Phase ごとの到達点

### Phase 1（基盤と初期生成）— 完了

「何もない状態から、統計に合った合成世帯と個人を生成できる」状態に到達しました。

- pydantic v2 ベースの設定ローダ（壊れた CSV を渡すと行番号付きでエラーが出る）
- `SeedRegistry` による階層的乱数管理（同じ seed なら bitwise 一致で再現）
- `PopulationArrays` + Registry + Household / Person のドメインモデル
- 9 種の `family_type` に対応する初期人口生成（SA を経ない段階での統計整合性は完全一致）
- `synthpop-jp quickstart` / `validate-config` の 2 サブコマンド

実例レポート: [`experiments/2026-04-25-quickstart-sample-case/report.md`](../../experiments/2026-04-25-quickstart-sample-case/report.md)

### Phase 2（SA MVP と性能ゲート）— 完了

初期生成した合成人口を、焼きなまし法（SA: Simulated Annealing、ランダムに少しずつ変更しながら段階的に良い解を探す確率的最適化）で統計に近づける機能と、その性能を担保する仕組みが揃いました。

- `AgeChangeTransition`（1 人の年齢を動かす遷移）と `ObjectiveState`（目的関数の差分更新）
- SA 1 step あたり 1.5 μs（差分更新による）、目標 100 μs を 67 倍上回る
- benchmark 一式（CI で smoke 版が毎 PR 走り、本格版は手動 `make bench`）
- メモリ実測（100k 世帯 × 200k 反復で 358MB、`trace.jsonl` は streaming で蓄積しない）
- HTML レポート基盤（plotly inline、self-contained で 1MB 以内）

ベンチマーク詳細: [`docs/reports/phase-02-benchmarks.md`](phase-02-benchmarks.md)
メモリ実測詳細: [`experiments/2026-04-29-sa-memory-profile/report.md`](../../experiments/2026-04-29-sa-memory-profile/report.md)

### Phase 3a（Murata 拡張: 作る軸）— 主要要件達成

SA に乗せる遷移と目的関数を、Murata 2017 論文 §11〜§12 の仕様に合わせて拡張しました。

- `AgeSwapTransition`（同じ家族類型・性別の 2 人の年齢を交換、§12.2B）
- `HybridTransition`（age-change と age-swap を確率混合、§12.2C 前半）
- 動的 `p_change` スケジュール（反復進行に応じて混合率を線形に変化、§12.2C 後半）
- extended objective 第 1 弾（family_type × sex pyramid を 10 統計追加）
- strict_extended モード（D, E 統計を除外、Murata 式(3) 準拠）
- 初期生成の F-W 統計誤差 0 化（決定論的 Largest Remainder で開始時点の誤差を 0 に）
- family_type × role × sex 分布の年齢サンプリング保証テスト

残っているのは extended objective の 21 統計フル対応と 9 family types フル対応です。

### Phase 3.5（評価器骨格）— 完了

「合成データを評価する」軸に 3 種類の指標が揃いました。

- `AggregateStatL1Evaluator`（統計別 L1 誤差レポータ、目的関数と同じ統計群）
- `RareCellEvaluator`（rare cell 監視、低頻度カテゴリへの過適合を検出）
- `CAP / TCAP Evaluator`（属性推論リスクのベースライン、Harada 2024 §5.2）
- `evaluate` サブコマンドが上記を順次呼ぶ形（`metrics.json` に書き出し）
- entry_points プラグイン機構（外部パッケージから評価器を差し込める）
- Table 13 形式の `report.md` 自動追記

### Phase 3b（比較 runner）— 完了

複数 config × 複数 seed の SA を回して、統計的に有意な差があるかを判定する仕組みが揃いました。

- `synthpop-jp compare <config>...` サブコマンド
- n=10〜30 seed の SA を並列実行
- Welch's t-test / Wilcoxon 検定 + Holm 補正
- bootstrap CI（percentile 法 2,000 回）

詳細な方法論まとめ: [`docs/reports/2026-04-29-phase3-extended-summary.md`](2026-04-29-phase3-extended-summary.md)

---

## 4. 実験結果ハイライト

### 実験 1: quickstart 初期生成（Phase 1 確認）

- 100 世帯 / 266 人の合成人口が約 1.1 秒で生成される
- 家族構成の分布が入力統計と完全一致（SA 前なので当然）
- HTML レポート（plotly 円グラフ + 人口ピラミッド + 整合性棒グラフ）が 1MB 以内で出力される

含意: 生成パイプラインの土台は安定しており、Phase 2 以降の SA はこの初期人口を出発点として使える。

詳細: [`experiments/2026-04-25-quickstart-sample-case/report.md`](../../experiments/2026-04-25-quickstart-sample-case/report.md)

### 実験 2: SA メモリプロファイル（Phase 2 後半）

- 100,000 世帯規模でも SA peak RSS は 358MB（物理 25.8GB の 1.4%）
- 反復回数を 20k → 200k に 10 倍してもメモリはほぼ不変（trace.jsonl が streaming である裏付け）
- HTML レポート生成は別プロセスで最大 179MB（100k 規模時）
- 100k × 200k は時間的には 12〜30 分かかる（O(N) 候補生成のオーバーヘッド）

含意: 「PC が固まる」のは SA 単独ではなく、複数の Claude Code エージェントとの同居が原因。100k 世帯以上は heavy 扱いとし、並列エージェントを控える運用ルールに反映済み（Issue #52）。

詳細: [`experiments/2026-04-29-sa-memory-profile/report.md`](../../experiments/2026-04-29-sa-memory-profile/report.md)

### 性能ベンチマーク（Phase 2 Exit gate）

| ベンチ | 実測 | 目標 | 結果 |
|---|---|---|---|
| `ObjectiveState.propose_change` | 1.5 μs | < 100 μs | 67 倍速い |
| `AgeChangeTransition.propose` | 7.5 μs | < 10 μs | 達成 |
| SA 1,000 世帯 × 20 万反復 | 5.2 s | < 30 s | 5.8 倍余裕 |

含意: 差分更新（O(1) 更新）が効いている証拠。21 統計フルに広げる場合でも、1 step あたりの差分計算は ~20% 増程度で収まることが PR #72 の実測で確認済み。

詳細: [`docs/reports/phase-02-benchmarks.md`](phase-02-benchmarks.md)

---

## 5. 残課題と次の方向性

### Phase 3a の残り

- **extended objective の 21 統計フル対応**: 現状 5+10 = 15 統計まで。残り 6 統計（spec §11.3 の式定義）
- **9 family types フル対応**: 現状 sample_case で扱う型のみ。残りの型を追加して `data/sample_case/` を拡張

### Phase 4 以降（構想中）

- **e-Stat 実データの取り込み配管**: `scripts/fetch_estat.py` を整備し、ダミーデータでなく国勢調査の実集計表で動かせるようにする
- **改善ループ（rule_based / Pareto）**: 評価結果を見て config を自動調整する Phase 5 の準備
- **mkdocs サイト化**: ドキュメント全体を Web で公開可能な形に

詳細な作業計画: [`docs/reviews/action-plan.md`](../reviews/action-plan.md) §3.5 以降

---

## 6. ドキュメント全体地図

### このプロジェクトを理解したい人向け

| 目的 | 参照先 |
|---|---|
| 何ができるか / インストール | [`README.md`](../../README.md) |
| 手法と CLI の使い方（本オーバービューと同じ並び） | [`docs/guides/how-it-works.md`](../guides/how-it-works.md) |
| 開発フロー全体像 | [`docs/getting-started/development-workflow.md`](../getting-started/development-workflow.md) |
| 仕様 | [`docs/spec/spec.md`](../spec/spec.md) |
| 評価指標の定義 | [`docs/spec/metrics.md`](../spec/metrics.md) |

### Phase ごとの実績を辿りたい人向け

| Phase | レポート |
|---|---|
| Phase 1 実例 | [`experiments/2026-04-25-quickstart-sample-case/report.md`](../../experiments/2026-04-25-quickstart-sample-case/report.md) |
| Phase 2 ベンチ | [`docs/reports/phase-02-benchmarks.md`](phase-02-benchmarks.md) |
| Phase 2 メモリ | [`experiments/2026-04-29-sa-memory-profile/report.md`](../../experiments/2026-04-29-sa-memory-profile/report.md) |
| Phase 3 中盤 handoff | [`docs/reports/2026-04-29-phase3-handoff.md`](2026-04-29-phase3-handoff.md) |
| Phase 3 拡張まとめ | [`docs/reports/2026-04-29-phase3-extended-summary.md`](2026-04-29-phase3-extended-summary.md) |

### 開発に参加する人向け

| 目的 | 参照先 |
|---|---|
| Issue 駆動フロー | [`docs/rules/issue-driven-development.md`](../rules/issue-driven-development.md) |
| TDD | [`docs/rules/tdd.md`](../rules/tdd.md) |
| worktree 配置 | [`docs/rules/git-worktree.md`](../rules/git-worktree.md) |
| ブランチ戦略 | [`docs/rules/branch-strategy.md`](../rules/branch-strategy.md) |
| 実験管理 | [`docs/rules/experiment-management.md`](../rules/experiment-management.md) |
| 文章スタイル | [`docs/rules/documentation-style.md`](../rules/documentation-style.md) |

---

## 7. このドキュメントの位置付け

- **オーバービュー（本ドキュメント）**: 現在地と方向性の 1 枚要約。読み手が次にどのドキュメントを開くべきかの分岐点
- **手法と使い方** ([`how-it-works.md`](../guides/how-it-works.md)): 「何をどう動かしているのか」を順を追って説明する読み物
- **個別レポート** (`docs/reports/*.md`): その時点の進捗チェックポイント。書き換えず、新しいスナップショットを追加していく

オーバービューは Phase の節目ごとに更新します（次回は Phase 4 着手時を想定）。
