# 3者レビュー統合アクションプラン

本ドキュメントは `docs/reviews/review-python.md` / `review-privacy.md` / `review-oss.md` の 3 視点レビューを統合し、**アウトプット（何を作るか）** と **順番（どの順で作るか）** を確定する統括計画書である。各指摘の詳細は元レビューを参照し、本書ではクロスレビューによる重複・対立の解消と、Phase 単位の確定タスクのみを扱う。

## 0. エグゼクティブサマリ

- spec.md は骨格は妥当だが、(i) 原論文式の記法ズレ、(ii) SA 内部表現の性能設計欠落、(iii) 秘匿性評価の既知バイアスと層別整理欠落、(iv) OSS 命名・ライセンス未定の 4 つが着手前のブロッカーである。
- 3 レビュアーが独立に **「Phase 0 新設」** を結論しており、これを採用する。Phase 0 で spec 改訂・基盤整備・契約文書を完了してから、現行 Phase 1 以降を NumPy 内部表現と Protocol 抽象の上に再構築する。
- 評価器は Phase 4 で一括ではなく、Phase 3 と Phase 4 の間に **Phase 3.5（評価器先出し）** を挟む。比較実験 (§15.1) の「正解」を評価器が決めるため、生成拡張より先に評価器骨格が要る。
- 現行 Phase 4 の privacy 実装順序は spec 記載順（DCR → NNDR → ...）ではなく、**rare cell → CAP → DCR/NNDR/ARD → MIA** に変更する。
- 改善ループ (§14) は rule-based を baseline、Pareto を MVP に格上げし、両者の比較を §15.3 実験 3 の主対象とする。

## 1. クロスレビューの整合

### 1.1 3 者が独立に合意した項目（強い結論）

| 論点 | Py | Priv | OSS | 確定方針 |
|---|:-:|:-:|:-:|---|
| Phase 0 新設 | ○ | ○ | ○ | 採用 |
| §11.4 式を訂正 | ○（スケール正規化） | ○（原論文式整合）| - | **両方**反映。原論文準拠モードを primary、rate 正規化 + weight は研究拡張モードとして分離 |
| §17 CLI 改善 | ○（resume 等） | - | ○（短縮・quickstart）| 両方採用 |
| 拡張ポイントの抽象化 | ○（Protocol）| ○（Evaluator Protocol）| ○（entry_points）| 内側 Protocol + 外側 entry_points の二層 |
| seed / 再現性の厳密化 | ○ | ○（事前登録）| ○（uv.lock/paper_results）| 全項目採用 |
| pydantic config + validate | ○ | - | ○ | `--validate-config` サブコマンド追加 |
| 評価器の距離定義明文化 | ○ | ○ | - | `docs/spec/metrics.md` を新設、Gower を primary |

### 1.2 対立の解消

- **型チェッカ**: Py は pyright 単独、OSS は mypy 併記 → **pyright strict 一本**に決定（Py 側の根拠がより具体）。
- **内部表現 vs 拡張性**: Py は「NumPy 並列配列」で固定、Priv/OSS は「差し替え可能性」を求める → I/O・拡張 API は `Protocol` / pydantic、SA 内部は並列配列、の**二層構造**で共存。Protocol はドメイン境界に、並列配列は `optimize/` 内に閉じる。
- **DP の扱い**: §3 で非目的だが Priv は将来拡張 API を要求 → 実装はせず、`Distribution` / `PrivacyMetric` Protocol だけ切っておく（コスト小・将来価値大）。
- **レビュー軽微の取捨**: `polars` 検討（Py 指摘15）、`kinship_id` 要否（Py 指摘13）は Phase 3 再判定に先送り。

### 1.3 命名の確定（OSS 指摘1 を Python / Priv の文面と整合）

- リポジトリ名: `synth-pop-harada-2024`（現状維持、研究期間中の実験リポ名として許容）
- PyPI / import 名: **`synthpop-jp`**（候補: `synthpop-jp`, `jpopsyn`, `mrsa-synth` → 本 PR では `synthpop-jp` を既定。Phase 0 で最終確認）
- CLI エントリポイント: `synthpop-jp`（`[project.scripts]` に登録）
- spec §9 のパッケージ名 `synthetic_population` は `synthpop_jp` に改名
- README 冒頭に「Murata 2017 の生成手法 + Harada 2024 の評価軸の Python 実装」と明記

## 2. アウトプット（work products）

成果物を 5 カテゴリに束ねる。各アイテムは責任 Phase とサイズ (S/M/L) を付す。

### A. spec 改訂（docs/spec/spec.md の差分）【Phase 0・S】

- §1: harada 2024 の位置付けを追加
- §5.3→§5.4 新設: 「Murata=生成側 / Harada=評価側 (ARD)」を明文化
- §6: Python 3.11+、パッケージ名 `synthpop-jp`、ライセンス Apache-2.0 を記載
- §7: 入力仕様は概要のみ残し、詳細は `docs/spec/data_contract.md` に委譲
- §9: ディレクトリツリーを改名、`domain/protocols.py`・`registry.py` を追加、plugin entry_points を記載
- §11.4 書き換え: 原論文準拠モード（weight 無し、rate×分母 Round）と研究拡張モード（セル数正規化 + weight）を分離明記
- §11.5: 禁止ペナルティは**ハード制約**として §12.2 に移動（Py 指摘14）
- §11.6 新設: 「目的関数最小化と秘匿性」(Priv 指摘4)
- §12: SA 差分更新が前提であることを明記
- §13.1: L1 primary、TV secondary を固定
- §13.3 を 3 層に再構成:
  - (a) 類似度 proxy: DCR / NNDR / ARD（Gower、proxy 注記）
  - (b) 属性推論 baseline: Generalized CAP / TCAP **← MVP 必須**
  - (c) shadow-based MIA: TAPAS / DOMIAS **← Phase 5 stretch**
- §14.3/§14.4: rule_based (baseline) / Pareto (MVP) / random_search を `improve.strategy` で切替
- §15: 事前登録必須、`docs/experiment_plan.md` を git tag でフリーズしてから Phase 3 着手する旨を明記
- §16: Phase 0 新設、Phase 3 を 3a/3.5/3b に分割、Phase 6 (v1.0 準備) を追加
- §17: `synthpop-jp` エントリ、`quickstart`, `validate-config`, `--resume`, `--dry-run`, `--log-level` を追加
- §18: pydantic モデル参照、デフォルト config と改善戦略列挙 (`rule_based | pareto | random_search`)
- §19: 回帰テストの許容幅と決定性テストを具体化
- §20: LICENSE, CITATION.cff, CHANGELOG, CODE_OF_CONDUCT, CONTRIBUTING, DATASET を追記

### B. 追加仕様・契約ドキュメント【Phase 0〜1・M】

- `docs/spec/data_contract.md`: 全 CSV の列・型・単位・欠損規則・family_type ↔ group マッピング・couple_diff 符号規則（Py 指摘2）
- `docs/spec/metrics.md`: 距離定義（Gower）、統計別損失式、proxy/baseline/MIA の 3 層整理（Priv 指摘2,3 / Py 指摘12）
- `docs/spec/experiment_report_format.md`: `compare` サブコマンド出力仕様、bootstrap CI の扱い（Py 指摘8）
- `docs/experiment_plan.md`: §15 の仮説・指標・検定・サンプルサイズの事前登録版（Priv 指摘8 / タスクE）
- `docs/assumptions.md`: 評価用 real-data protocol（semi-synthetic 設定、hold-out 出所、IRB）、e-Stat 利用規約、統計法 §44 出典義務（Priv S5/S6 / OSS 指摘2）
- `docs/adr/0001-internal-representation.md`, `0002-objective-normalization.md`, `0003-privacy-evaluation-layers.md`, `0004-naming-and-license.md`: 意思決定の根拠記録（Py タスクF）

### C. プロジェクト基盤（ルート）【Phase 0・M】

- `pyproject.toml`: `[project.scripts] synthpop-jp = "synthpop_jp.cli:app"`, `[project.entry-points."synthpop_jp.evaluators"]`, `[project.entry-points."synthpop_jp.transitions"]`, `[project.entry-points."synthpop_jp.family_types"]`, `[dependency-groups] dev/test/docs`
- `uv.lock`（commit）
- `LICENSE`（Apache-2.0）、`NOTICE`（依存クレジット）
- `README.md`（日本語 primary、英語セクション併記、30 秒 Quickstart、比較表）
- `CITATION.cff`, `CODE_OF_CONDUCT.md`（Contributor Covenant）, `CONTRIBUTING.md`（拡張例つき）, `CHANGELOG.md`（Keep a Changelog + SemVer）, `DATASET.md`（e-Stat 取扱い、sample_case 由来）
- `Makefile`（`make quickstart`, `make paper`, `make docs`）
- `.github/workflows/ci.yml`（uv sync → ruff → pyright → pytest → benchmark）, `release.yml`（tag → PyPI）
- `.github/ISSUE_TEMPLATE/{bug,feature,new-family-type,new-evaluator}.yml`, `PULL_REQUEST_TEMPLATE.md`
- `.pre-commit-config.yaml`（ruff, ruff-format, pyright local, check-yaml, check-added-large-files, nbstripout）
- `.ruff.toml`, `pyrightconfig.json`

### D. タスク台帳【Phase 0・S】

ユーザーのグローバル規約に従い `docs/tasks/phase-NN/task-MMM.md` を生成。Phase 0 の task-001 〜 task-008 と、後続 Phase の骨子を先置きする。詳細は本書 §3 参照。

### E. 実装成果物【Phase 1 以降】

- Phase 1: `src/synthpop_jp/{io,domain,init,config}/...`、pydantic ローダ、ダミー入力、random initial population、`synthpop-jp quickstart`
- Phase 2: 差分更新版 objective (minimal)、age-change、SA runner、`trace.jsonl`、`rich` 進捗
- Phase 3a/3b: age-swap、hybrid、extended objective、比較 runner、21 統計別誤差レポータ
- Phase 3.5: 評価器骨格（`aggregate_metrics`, `utility_metrics`, `privacy_metrics` のインターフェース + CAP 先行実装）
- Phase 4: broad/narrow utility、rare cell、CAP、DCR/NNDR/ARD、report generator
- Phase 5: rule_based tuner、Pareto、multi-trial、best config 選択、experiments 3/4
- Phase 6: `paper_results/` 固定、Zenodo DOI、英語ドキュメント完備、v1.0 タグ

## 3. 順番（Phase 再編とゲート条件）

### 3.1 全体フロー

```
Phase 0  →  Phase 1  →  Phase 2  →  Phase 3a  →  Phase 3.5  →  Phase 3b  →  Phase 4  →  Phase 5  →  Phase 6
基盤+spec    I/O+初期生成  SA MVP     age-swap      評価器骨格     比較runner   評価器本体   改善ループ   v1.0準備
```

並列可能箇所: Phase 3a と Phase 3.5 は評価器 API 固定後は並列、Phase 4 の utility/privacy は独立、Phase 5 の rule_based と Pareto は並列。

### 3.2 Phase 0（新設・目安 3〜5 日）

**目的**: ブロッカー全排除。Phase 1 の実装中に仕様・基盤の手戻りを起こさない。

タスク（ゲート: 全完了で Phase 1 着手）:
- `task-001` spec 改訂（§2A を反映）
- `task-002` data_contract / metrics / experiment_plan / assumptions の骨子作成
- `task-003` プロジェクト命名・LICENSE・CITATION 確定（ADR-0004）
- `task-004` pyproject.toml + uv.lock + ruff + pyright + pre-commit 構築
- `task-005` GitHub Actions (CI + release) skeleton と Issue/PR テンプレ
- `task-006` README 骨子（日英併記、比較表、30 秒 Quickstart 記述先行）
- `task-007` `src/synthpop_jp/` ディレクトリ骨格と `domain/protocols.py`（空定義でよい）
- `task-008` ADR 0001〜0004 記述

**Exit 条件**: `uv sync --frozen && ruff check && pyright && pytest` が空 CI で緑。spec.md の差分が merge 済み。

### 3.3 Phase 1（I/O + 初期生成・目安 1 週）

タスク:
- pydantic v2 ローダ（全 CSV、`TypeAdapter` + 行番号付きエラー）
- `PopulationArrays`（NumPy 構造化配列 / 並列配列、ADR-0001 準拠）
- domain ↔ 並列配列のコンバータ
- `family_type_group` yaml マッピングと `register_family_type` API
- ランダム初期人口生成（§10.1 step 1〜6）
- `synthpop-jp quickstart` サブコマンド（sample_case で 10 秒生成）
- `synthpop-jp validate-config`
- sample_case ダミー生成スクリプト（`scripts/generate_sample_case.py`、seed 固定）
- e-Stat adapter の skeleton（OSS タスクB、実体は Phase 2〜3 で追加可）

**Exit 条件**: ダミー入力 → 初期人口 → `synthetic_households.csv` / `synthetic_persons.csv` が出力、決定性テスト（同 seed で bitwise 一致）緑。

### 3.4 Phase 2（SA MVP・目安 1.5 週）

タスク:
- 目的関数 minimal 版（§11.2、原論文準拠モード、差分更新、`ObjectiveState`）
- age-change 遷移（§12.2A）
- SA runner（Metropolis, 停止条件 §12.3）
- `trace.jsonl` + `rich.live` 進捗
- `--resume` / checkpoint（10k 反復ごと、`artifacts/checkpoint/*.parquet`）
- pytest-benchmark: 1,000 世帯 × 20 万反復 ≤ 30 秒のベンチ（Py タスクB）
- hypothesis property test（遷移後の household size 不変、差分更新と全再計算の一致、Py タスクD）

**Exit 条件**: §15.1 実験 1 の骨格が回る（evals_per_agent = 1000 で 1 seed の best_score が初期の 30% 以下）、ベンチ合格、決定性テスト緑。→ **v0.1 (alpha) tag + PyPI**。

### 3.5 Phase 3a（Murata 拡張・目安 1 週）

タスク:
- age-swap 遷移（§12.2B）
- hybrid 遷移（§12.2C、`p_change` / `p_swap` スケジュール）
- family type × role × sex 分布からの年齢サンプリング
- extended objective（§11.3、21 統計、原論文式(3)）
- 初期生成の 21 統計誤差 0 化（Priv S2）

**Exit 条件**: age-change/age-swap/hybrid を切替可能、21 統計ブレークダウン出力可。

### 3.6 Phase 3.5（評価器骨格・目安 0.5 週、Phase 3a と一部並列可）

タスク:
- `Evaluator` Protocol と `evaluate/` モジュール skeleton
- 統計別 L1 誤差レポータ（Table 13 形式）
- **CAP 先行実装**（Priv 指摘3、DCR より先）
- rare cell 監視メトリクス（Priv タスクF）
- `metrics.json` スキーマ + `report.md` テンプレート
- 評価 plugin entry_points テスト

**Exit 条件**: `synthpop-jp evaluate --run-dir ...` で Table 13 形式と rare cell + CAP を出力可。

### 3.7 Phase 3b（比較 runner・目安 0.5 週）

タスク:
- `synthpop-jp compare` サブコマンド（`docs/spec/experiment_report_format.md` 準拠）
- seed 群を回す runner（n=10〜30）、Welch's t + Holm 補正（Priv 指摘8）
- bootstrap CI の report 出力
- §15.1 実験 1・§15.2 実験 2 を再現

**Exit 条件**: `experiment_plan.md` を git tag でフリーズし、実験 1/2 の結果が `paper_results/` に固定コミットされる。

### 3.8 Phase 4（評価器本体・目安 1.5 週、utility と privacy を並列）

- Phase 4a（utility）:
  - broad utility: mixed-type 相関 (dython 準拠)、全属性ペア TV、Frobenius 差
  - narrow utility: 固定 3 タスク (family_type 分類 / household_size 回帰 / role 予測) の TSTR・TRTS
- Phase 4b（privacy、実装順序: rare cell → **CAP**（既済）→ DCR/NNDR/ARD → MIA skeleton）:
  - `domain/distance.py`（Gower）
  - DCR / NNDR / ARD（ARD は Harada 2024 準拠で出典明記）
  - shadow seed 群で MIA 評価の実験 protocol を documentation のみ整備（実装は Phase 5）
- `report.md` ジェネレータに出典セクション・ライセンス注記を自動埋め込み
- mkdocs サイト v0.2（日英併記、3 本の tutorial notebook）
- **→ v0.2 tag**。

### 3.9 Phase 5（改善ループ・目安 1.5 週）

- `improve/strategy.py` の 3 戦略: `rule_based` / `pareto` / `random_search`
- multi-trial runner（n=10〜30）と best config 選択
- Pareto フロント可視化（`outputs/*/pareto.png`）
- §15.3 実験 3（rule_based vs Pareto）
- §15.4 実験 4（複数候補のばらつき）
- MIA 実装（TAPAS / DOMIAS、stretch）
- → **v0.3 tag**。

### 3.10 Phase 6（v1.0 準備・目安 1 週）

- `paper_results/` 固定（`Makefile` で再現）
- Zenodo 連携、DOI 発行、`CITATION.cff` 更新
- 英語ドキュメント完備、SDV 比較 end-to-end ベンチ
- v1.0 release & PyPI stable

## 4. 責任分担（チーム編成）

単一執筆者プロジェクトである前提で、思考モード（ロール）として分業する。各 Phase で以下のロールを切り替え、ADR に決定根拠を残す。

| ロール | 担当範囲 | 主参照レビュー |
|---|---|---|
| **Implementer (Python)** | §9 実装、Protocol、SA、ベンチ、テスト、ツールチェイン | review-python.md |
| **Researcher (Privacy)** | §11 式、§13 評価器、§15 実験設計、ADR-0002/0003 | review-privacy.md |
| **Maintainer (OSS)** | 命名、LICENSE、README、CI、docs サイト、plugin、CITATION | review-oss.md |

Phase 0 は 3 ロール全員が関与、Phase 1〜2 は Implementer 主、Phase 3 以降は Researcher 主、Phase 4〜5 末および Phase 6 は Maintainer 主、が重心となる。

## 5. リスクと打ち手

| リスク | 指摘元 | 打ち手 |
|---|---|---|
| SA 内ループが遅く §15 実験が現実的時間に収まらない | Py 指摘1 | Phase 0 task-007 の段階で差分更新 PoC を 1 日スパイク。合格基準未達なら並列配列表現を再設計 |
| 原論文式の誤実装で再現失敗 | Priv 指摘1 | Phase 0 task-001 で §11.4 を両モード分離、Phase 3b で Table 13 形式比較を必ず出す |
| 評価用実個票の入手不可で DCR/CAP が算出不能 | Priv 指摘2 | Phase 0 で assumptions.md に semi-synthetic プロトコル明記。hold-out が揃わない間は CAP を marginal ベースで近似 |
| 命名・ライセンス後追いで破壊的変更発生 | OSS 指摘1,2 | Phase 0 task-003 で確定、v0.x 中は SemVer の破壊的変更を CHANGELOG で明示 |
| e-Stat 規約違反 | OSS 指摘2, Priv S5 | sample_case を完全ダミー化、実データは `scripts/fetch_estat.py` でユーザー取得。`report.md` に出典自動埋込 |
| テストが seed に過剰依存し依存更新で破綻 | OSS 指摘7, Py 指摘10 | 決定性テスト (bitwise) と許容幅テスト (±1%) を分離、`uv.lock` 固定、CI で lock を frozen |

## 6. 直近の具体アクション（本レビュー直後の 3 日分）

1. 本 action-plan.md のレビュー確認と合意（ユーザー判断事項: PyPI 名 `synthpop-jp` 採用可否、LICENSE Apache-2.0 採用可否）
2. Phase 0 task-001〜008 を `docs/tasks/phase-00/task-001.md` 〜 `task-008.md` に展開（ユーザー規約準拠）
3. spec.md 改訂の PR（§2A の箇所、本書で指摘した差分のみを対象）
4. `docs/spec/data_contract.md` / `docs/spec/metrics.md` / `docs/experiment_plan.md` / `docs/assumptions.md` の骨子（章立てのみ）を先行配置
5. ADR-0001〜0004 の執筆（決定根拠を凍結）

本書はこれ以降、仕様変更があれば ADR で追補し、本書自体は Phase 0 完了時点で「実行済み」とマークする。
