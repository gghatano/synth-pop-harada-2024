# synthpop_jp/

`synthpop-jp` 本体パッケージ。Murata 2017 系の合成人口生成と Harada 2024 系の評価軸を「作る／整える／評価する」の 3 軸に分けて実装しています。

## モジュール構成

### エントリポイント

| ファイル | 役割 |
|---|---|
| `cli.py` | `synthpop-jp` コマンド本体（typer ベース、`quickstart` / `generate` / `validate-config` / `evaluate` / `compare` サブコマンド） |
| `config.py` | YAML 設定の pydantic モデル（型と検証は `docs/spec/spec.md` §18 に対応） |
| `registry.py`, `rng.py` | ID レジストリと SeedRegistry（同 seed で bitwise 一致の決定性を保証） |

### ドメイン層 — `domain/`

純粋な値オブジェクト・Protocol・距離関数。他層から共通参照される。

- `protocols.py` — `Transition` / `Evaluator` / `PrivacyMetric` の 3 つの Protocol（プラグイン境界）
- `family_types.py`, `household.py`, `person.py` — ドメインモデル
- `registry.py`, `statistics.py` — 配列ベース表現と統計集計
- `distance.py` — 混合型レコードに対する Gower 距離（DCR/NNDR/ARD で前計算）

### I/O 層 — `io/`

- `schemas.py` — pydantic v2 スキーマ（行番号付きエラー）
- `loaders.py` — CSV → `PopulationArrays` のロード
- `writers.py`, `synthesized.py` — 出力 CSV の書き出しと再構築

### 初期生成 — `init/`

決定論的 Largest Remainder で SA 開始時点の F-W 統計誤差を 0 にする。

- `initial_population.py` — 9 family_type からの世帯生成
- `household_sampler.py` — family_type × role × sex 別の年齢サンプラ

### 作る軸（最適化） — `optimize/`

| ファイル | 役割 |
|---|---|
| `annealing.py` | SA runner（Metropolis、停止条件 §12.3） |
| `cooling.py` | ExponentialCooling など温度スケジュール |
| `transitions.py` | AgeChange / AgeSwap / Hybrid 遷移（§12.2） |
| `objective.py` | 目的関数（minimal / extended / strict_extended）と stats 集計 |
| `state.py` | `ObjectiveState` の O(1) 差分更新 |
| `trace.py` | `trace.jsonl` への streaming 進捗ログ |
| `checkpoint.py` | `--resume` 用の中間状態保存 |

### 評価する軸 — `evaluate/`

3 層の評価器。すべて `Evaluator` Protocol を実装し、entry_points 経由で外部からも差し込める。

| ファイル | 層 | 役割 |
|---|---|---|
| `aggregate_metrics.py` | 統計整合性 | 統計別 L1 誤差（Table 13 形式 report.md 自動追記） |
| `rare_cell_metrics.py` | 統計整合性 | rare cell（低頻度カテゴリ）監視 |
| `utility_metrics.py` | 有用性 | broad utility（mixed-type 相関 / pair-TV / Frobenius 差） |
| `downstream_tasks.py` | 有用性 | narrow utility（TSTR / TRTS の固定 3 タスク） |
| `attribute_inference.py` | 秘匿性 | CAP / TCAP（属性推論リスク baseline） |
| `privacy_metrics.py` | 秘匿性 | DCR / NNDR / ARD（Gower 距離ベース） |
| `plugin.py` | — | entry_points プラグインの解決 |

### 比較・改善・報告

| サブパッケージ | 役割 |
|---|---|
| `compare/` | n seed × 複数 config の SA を回し、Welch / Wilcoxon + Holm 補正 + bootstrap CI 付き比較レポートを出す |
| `improve/` | rule_based / Pareto / random_search 改善戦略の skeleton（実体化は今後） |
| `reports/` | markdown / HTML / plot 生成（plotly inline、self-contained ≤ 1MB） |
| `experiments/` | 実験用の補助関数 |

## 拡張する

新しい遷移・評価器を追加するときは、対応する Protocol を実装したクラスを書き、`pyproject.toml` の `[project.entry-points."synthpop_jp.transitions"]` または `synthpop_jp.evaluators` に登録するだけです。詳細は [`CONTRIBUTING.md`](../../CONTRIBUTING.md) を参照してください。
