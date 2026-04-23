# Python エンジニア視点レビュー

## サマリ（3〜5行）

本 spec は研究用プロトタイプとしての骨格はよくできているが、実装者が着手した瞬間に詰まる箇所が複数ある。特に (a) §8 のデータモデルが `list[Person]` の OOP 構造のまま §11.4 の目的関数評価（都度の集計）に流れ込むと SA 内ループで致命的に遅くなる、(b) §7.1 の CSV スキーマが緩く（`rate_or_count` のような型ゆらぎを残した列名）ローダ実装が発散する、(c) §19 のテスト仕様が SA の確率性・seed 契約に踏み込んでいない、という 3 点が最大の懸念。Phase 1 着手前にデータ表現・CSV contract・seed 契約の 3 点を確定させることを強く推奨する。

## 重大な指摘（実装前に直すべき）

- 【指摘1】SA 内部表現は「NumPy の構造化配列 / 並列配列」に固定すべき（§8, §11.4, §12）
  - 現状: §8 で `Household.members: list[Person]` という OOP 表現、§11.4 の目的関数は `sum_s sum_j weight_s * abs(observed[s,j] - target[s,j])` と集計ベース。§12 の SA は `max_iters: 200000`（§18）で回す。
  - 問題: 1 遷移ごとに `list[Household]` を走査して `observed[s,j]` を再集計すると、N=数千世帯 × 20 万反復で確実に非現実的な速度になる。`Person` を pydantic モデルにした場合はさらに遅い（dataclass の 5〜10 倍）。また §11.5 の「親が子より若い」判定も世帯内ペアを毎回走査すると重い。
  - 提案:
    - ドメインモデル（I/O・外部 API 用）と SA 内部表現を**分離**する。I/O 層は pydantic v2 `BaseModel`（バリデーション目的）、SA 内部は以下の並列配列で固定：
      ```python
      # optimize/state.py
      @dataclass
      class PopulationArrays:
          age: np.ndarray          # int16, shape=(n_persons,)
          sex: np.ndarray          # int8 (0=M,1=F)
          role: np.ndarray         # int8 (enum)
          household_id: np.ndarray # int32
          family_type: np.ndarray  # int8 (enum, person-broadcast)
      ```
    - `observed[s,j]` は**差分更新**する。遷移前後で影響を受けるビン（age_bin, sex, family_type）だけを `+1 / -1` し、`abs` の総和を保持変数 `score` に差分反映。これで1遷移 O(1)。§12.1 の `evals_per_agent` 上限も差分前提で初めて現実的。
    - 差分更新ロジックは `optimize/objective.py` に `ObjectiveState` クラスとして閉じ込め、`propose / accept / reject` の 3 メソッド API で §12.2 の全遷移を扱えるようにする。

- 【指摘2】§7.1 の CSV スキーマが曖昧で、ローダ実装が分岐する
  - 現状: `age_diff_parent_child.csv` の `rate_or_count` 列、`diff_bin` のビン定義、`age_diff_couple.csv` の `diff` の符号規則（夫-妻か妻-夫か）、`family_type` 文字列の正規化規則が未定義。`family_type_group`（§7.1 #2）と `family_type`（§7.1 #1, §8.1）の対応表もない。
  - 問題: Phase 1 の入力ローダ実装（§16 Phase 1）で必ず止まる。ダミーデータと実データで列型が変わると pydantic バリデーションも組めない。
  - 提案:
    - §7.1 を「rate 列 or count 列の**どちらか片方のみ**を許す」に確定し、ローダは両対応で内部的に rate へ正規化する。
    - `diff_bin` は `"[-5,-3)"` のような半開区間文字列か、`diff_min:int, diff_max:int` の2列に変更。前者なら `pandas.Interval` にパース。
    - `couple_diff = husband_age - wife_age` と符号規則を明記。
    - `family_type_group` は `docs/spec/data_contract.md` として切り出し、`family_type` → `group` のマッピング表を yaml で配布（`data/mappings/family_type_group.yaml`）。
    - pydantic v2 の `TypeAdapter(list[FamilyTypeCountRow])` でスキーマ検証、失敗時は行番号付きエラーを `rich` で出す。

- 【指摘3】Seed 契約と乱数源が未定義（§10.2, §18, §19.3）
  - 現状: §10.2 に「seed を固定可能にする」、§18 に `seed: 42` とあるのみ。§14.1 のループは trial ごとに何をどう再シードするか書かれていない。§19.3 の「主要メトリクスの大幅劣化がない」は seed 固定の再現性テストとしては曖昧。
  - 問題: `numpy.random.default_rng` と Python 標準 `random` と `scipy.stats` が混在すると、trial 再現ができず §15 の実験結果に再現性担保ができない。並列 trial 実行時の seed 衝突も論点になる。
  - 提案:
    - `np.random.Generator` のみを使用し、`random`/`scipy.stats.random_state` は禁止（lint ルールで ban）。
    - `SeedSequence` による階層 seeding を仕様化：
      ```python
      root_ss = np.random.SeedSequence(config.seed)
      init_rng, sa_rng, eval_rng = root_ss.spawn(3)
      trial_ss = root_ss.spawn(config.improve.trials)
      ```
    - `metrics.json` に `seed`, `numpy_version`, `git_sha` を必ず記録。§19.3 は「同一 seed・同一 input → 同一 `best_score`（bitwise）」の決定性テストに書き換える。

- 【指摘4】§11.4 の式が「距離関数」として曖昧（L1 / MAE / 重み付けの単位）
  - 現状: `sum_s sum_j weight_s * abs(observed[s,j] - target[s,j])` のみ。`observed` が count か rate か、`weight_s` が統計間スケール差を吸収する定数か、がどこにも書いていない。§18 の weights は `demographic: 0.5` と `family_type_demographic: 1.5` のように値域が揃っていない前提で書かれている。
  - 問題: 統計ごとにセル数が桁違い（demographic pyramid 200セル vs couple_gap 40セル）で、生の L1 和を取ると demographic が支配する。Phase 2 で weight 調整に数日溶ける。
  - 提案:
    - 目的関数を「**rate ベース L1** / セル数で正規化」に変更し、spec に次式を明記：
      ```
      loss_s = (1 / |cells_s|) * sum_j |observed_rate[s,j] - target_rate[s,j]|
      objective = sum_s weight_s * loss_s
      ```
    - `observed` は count を人口総数で割って rate 化。§11.4 を書き換え、§18 の weight 意味を「統計間相対重要度」と明記。

- 【指摘5】§9 のアーキテクチャに「protocols / interfaces」が無く、§14.2 の改善ループが差し込めない
  - 現状: `optimize/transitions.py` と `improve/strategy.py` が具体モジュールとして書かれているだけで、遷移・冷却スケジュール・tuner が抽象として定義されていない。§22 の「追加評価器を差し込みやすい構成」に反する。
  - 提案: `domain/protocols.py`（または `optimize/protocols.py`）に `typing.Protocol` で契約を明示：
    ```python
    class Transition(Protocol):
        def propose(self, state: PopulationArrays, rng: Generator) -> Proposal: ...
        def apply(self, state: PopulationArrays, p: Proposal) -> None: ...
        def revert(self, state: PopulationArrays, p: Proposal) -> None: ...

    class CoolingSchedule(Protocol):
        def temperature(self, iter: int) -> float: ...

    class Evaluator(Protocol):
        name: str
        def evaluate(self, pop: PopulationArrays) -> dict[str, float]: ...
    ```
    これで §14.3 の rule-based tuner は `list[Evaluator]` と `list[Transition]` を差し替えるだけで機能する。

## 中程度の指摘（Phase 1〜2中に対応すべき）

- 【指摘6】§18 の config を pydantic-settings + yaml で一本化する
  - yaml から pydantic モデルへ読み込み、CLI（§17）の `--config` は `pydantic_settings.BaseSettings` でオーバーライド可能にする。`annealing.cooling_rate` のような値は `Field(gt=0, lt=1)` でバリデーション。未定義キーは `extra="forbid"`。

- 【指摘7】§17 の CLI に `--resume` / `--dry-run` / `--log-level` が無い
  - §12.1 の `max_iters: 200000` を回した途中で落ちた場合の復旧手段が無い。`outputs/run_001/checkpoint.parquet` を 10k 反復ごとに書き、`generate --resume outputs/run_001` で再開できるようにする。`artifacts/` (§7.2 #5) の中身が未定義なので、`checkpoint/`, `trace/`, `figures/` のサブディレクトリ規約を §7.2 に追記。

- 【指摘8】§17 の `compare` サブコマンドの入出力が未定義
  - `--experiment configs/compare_age_change_swap.yaml` とあるが、複数 run の diff レポート形式、metrics の集計ルール、有意差判定（bootstrap CI か単純平均か）が未定。Phase 3 の「比較実験 runner 実装」の前に `docs/spec/experiment_report_format.md` を追加する。

- 【指摘9】進捗表示は `rich.progress` に統一、`tqdm` は禁止
  - §6.2 に両方を入れないこと。SA 内ループのログは 1 万反復ごとに `rich.live` で `temperature / score / accept_rate` を更新、JSON Lines で `trace.jsonl` に追記。

- 【指摘10】§19.2 の「SA 実行で best score が初期値以下になる」は弱すぎる
  - 単調に下がるのは当たり前なので回帰テストにならない。「初期 score の 30% 以下に収束」など absolute な閾値を 1 つ、「seed=42 で best_score が baseline_metrics.json と一致」の決定性テストを 1 つ、合計 2 本に分ける。

- 【指摘11】§13.2 Narrow utility の「ダミー目的変数」が未定義
  - ダミー変数の生成ルール（例: `y = 1[age >= 65]` のような関数）を `evaluate/downstream_tasks.py` の docstring 規約として固定。そうしないと Phase 4 で task が発散する。

## 軽微な指摘（Phase 3以降で良い）

- 【指摘12】§13.3 の privacy 指標（DCR, NNDR, ARD）の距離定義（Gower / HEOM など）を `docs/spec/metrics.md` に明記。混合型データなので Euclidean では不可。
- 【指摘13】§8 の `kinship_id: Optional[str]` の用途が不明。Phase 3 以降で使うなら §10.1 のどこで割り当てるかを追記、使わないなら削除。
- 【指摘14】§11.5 の「禁止ペナルティ」は目的関数に加えると温度チューニングに干渉する。**ハード制約**（遷移前に弾く）として §12.2 に移す方が健全。
- 【指摘15】§6.2 に `polars` 検討を追加。入力規模が小さいなら pandas でよいが、`persons` が数十万行になると I/O で差が出る。
- 【指摘16】§20 に `pyproject.toml`, `uv.lock` が明記されていない。

## 追加で必要と考えるタスク

- タスクA: **CSV data contract 策定**（`docs/spec/data_contract.md`, `data/sample_case/schema.json`）
  - 目的: 指摘2 の解消。全 CSV の列・型・単位・欠損規則を JSON Schema で固定。
  - 成果物: schema.json, pydantic モデル, サンプル CSV 一式
  - 規模: S

- タスクB: **NumPy 内部表現と差分更新目的関数の PoC**
  - 目的: 指摘1 の検証。1,000 世帯で 20 万反復が 30 秒以内に収まるかベンチ。
  - 成果物: `benchmarks/sa_bench.py`, pytest-benchmark 統合
  - 規模: M

- タスクC: **Seed 契約テスト**（`tests/test_determinism.py`）
  - 目的: 指摘3 の検証。同一 config で 2 回走らせて全メトリクス bitwise 一致を assert。
  - 成果物: CI で常時走るテスト
  - 規模: S

- タスクD: **hypothesis による property test**
  - 目的: 「age-swap 後に2人の age が交換される」「household size は全遷移で不変」「目的関数差分更新と全再計算が一致」を確率的に検証。§19.1 の単体テストより遷移バグを拾いやすい。
  - 成果物: `tests/property/test_transitions.py`
  - 規模: M

- タスクE: **Config schema 自動ドキュメント生成**
  - 目的: pydantic モデル → Markdown 自動生成で §18 を常に最新に。
  - 成果物: `scripts/gen_config_docs.py`, pre-commit hook
  - 規模: S

- タスクF: **CONTRIBUTING.md / ADR ディレクトリ**
  - 目的: 「なぜ NumPy 配列表現か」「なぜ pydantic v2 か」を ADR 化。`docs/adr/0001-internal-representation.md` など。
  - 規模: S

## Phase 順序への提案

現行 §16 の Phase 1〜5 は「ダミー入力 → SA → 評価 → 改善」の縦割りで、指摘1〜3 の基盤が後回しになる。以下に再編を提案する。

- **Phase 0（新設・0.5 週）**: data contract（タスクA）、seed 契約（タスクC）、内部表現 PoC（タスクB）、pyproject/uv/ruff/pyright/pre-commit 整備。ここを通さないと Phase 2 で必ず手戻る。
- **Phase 1（現行 Phase 1 + I/O テスト）**: pydantic ローダ、domain モデル、並列配列コンバータ、ランダム初期人口生成。ダミー入力は Phase 0 の schema に従う。
- **Phase 2（現行 Phase 2）**: **差分更新版**目的関数 minimal → age-change → SA、`trace.jsonl` と `rich` 進捗。ここで §15.1 の実験 1 が回ることを MVP とする。
- **Phase 3（現行 Phase 3 を分割）**:
  - 3a: age-swap + hybrid + family type 別分布
  - 3b: extended objective + 比較 runner（実験 1, 2）
- **Phase 4（現行 Phase 4）**: broad utility → privacy proxy → report。§13.2 Narrow utility は Phase 4b として分離、ダミー目的変数の仕様固定が前提。
- **Phase 5（現行 Phase 5）**: rule-based tuner → multi-trial → best config 選択 → 実験 3, 4。

並列化可能性: Phase 3a と 3b は独立、Phase 4 の privacy と utility も独立。Phase 0 完了後は 3 人並列まで可能。詰まりやすいのは **Phase 2 の差分更新実装**（指摘1）と **Phase 4 の privacy 距離定義**（指摘12）。

## 推奨ツールチェイン

- **パッケージ管理**: `uv`（§6.1 準拠）。`pyproject.toml` に `[tool.uv]`, `[dependency-groups]` で `dev`, `test`, `docs` 分離。`uv.lock` コミット。
- **Lint/Format**: `ruff` を一本化（`ruff check` + `ruff format`）。ルール: `E,F,W,I,N,UP,B,SIM,RUF,NPY,PD,PT`。`NPY201` で NumPy 2.x 準拠、`PD` で pandas アンチパターン検知。
- **型**: `pyright`（strict モード、`reportMissingTypeStubs=warning`）。`mypy` と両方動かすと冗長なので pyright 一本。CI でブロック。
- **テスト**: `pytest` + `pytest-benchmark`（指摘タスクB）+ `hypothesis`（タスクD）+ `pytest-xdist`（並列）+ `pytest-cov`（閾値 80%）。`tests/unit`, `tests/integration`, `tests/property`, `tests/regression` の 4 階層。
- **pre-commit**: `ruff`, `ruff-format`, `pyright`（local hook）, `check-yaml`, `check-added-large-files`（CSV は 500KB 以下）, `nbstripout`（notebook 混入対策）。
- **CI**: GitHub Actions、`uv sync --frozen` → `ruff` → `pyright` → `pytest -n auto --cov` → `pytest-benchmark compare`（基準ファイルコミット）。matrix は Python 3.11 / 3.12。
- **docstring**: `numpydoc` スタイル統一、`ruff` の `D` ルールで強制（`D415` まで）。公開 API のみ必須、private は省略可。
- **実行時ロギング**: `structlog` + `rich` console renderer。`outputs/run_xxx/run.log`（JSON Lines）に機械可読ログ、stdout は人間可読。
