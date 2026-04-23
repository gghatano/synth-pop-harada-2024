# OSS 普及エンジニア視点レビュー

## サマリ（3〜5行）

spec.md は研究プロトタイプとしての実装仕様は整っているが、OSS として公開・普及するための「命名」「ライセンス」「入口UX」「拡張ポイント」「再現性メタデータ」の記述が欠落している。特にリポジトリ名 `synth-pop-harada-2024` とパッケージ名 `synthetic_population`、さらに PyPI 候補名が三重にズレており、放置すると検索性・引用・Googleabilityに致命的に効く。上流の `synthpop`（R）, `SDV`, `pop-synth` 系と何が違うのかを Abstract レベルで明記し、日本の e-Stat / 国勢調査という具体ドメインに特化した差別化を v0.1 の時点から打ち出すべき。また harada 2024 論文（仮想都市データの ARD 評価）との関係を README 冒頭で明示することで、研究系ユーザーの獲得コストを大きく下げられる。

## 重大な指摘（Phase 1 開始前に決めるべき）

### 【指摘1】プロジェクト命名とパッケージ名の三重ズレ

- **現状**: リポジトリ名 `synth-pop-harada-2024`、spec §9 のパッケージ名 `synthetic_population`、CLI エントリは §17 で `python -m synthetic_population.cli`。PyPI 公開時の名前は未定義。
- **問題**: (a) `synthetic_population` は PyPI の一般語すぎて取得できても紛らわしく、類似OSS（`synthpop`, `population_synthesis`, `pop-synth`, `SynPop`）に埋もれる。(b) ディレクトリ名の "harada-2024" は harada 2024 論文（`docs/papers/harada_2024.pdf`: 仮想都市データの有用性・秘匿性評価）を強く想起させるが、spec §1〜§5 は Murata 2017 の再現がコアで harada 2024 への言及がゼロ。読者は「どっちの論文の実装なのか」分からない。(c) 引用時に `synthetic_population` だけでは Googleable でなく、DOI や論文参照に耐えない。
- **提案**:
  - PyPI / import 名を統一する。例: `jpopsyn`（Japan Population Synthesis）、`synthpop-jp`、`mrsa-synth`（Murata SA）、`harapop` などから1つ選定し spec §6・§9・§17 を書き換える。
  - リポジトリ名の "harada-2024" は harada 2024（ARD 評価）をモジュール `evaluate/privacy_metrics.py` の設計指針として参照している旨を spec §1・§5.3・§13.3 に追記する。spec §13.3 の "ARD" は harada 2024 由来の評価軸であることを脚注化。
  - README 冒頭に "A Python re-implementation of Murata et al. (2017) synthetic population generator, with usability/privacy evaluation following Harada et al. (2024)" という一文を置く。

### 【指摘2】ライセンスと再配布ポリシーの未定義

- **現状**: spec §20 成果物リストに LICENSE が無く、依存ライブラリ（§6.2: pandas, scipy, scikit-learn, matplotlib 等）のライセンス整合も未記載。spec §21 の「実統計」再配布可否に触れていない。
- **問題**: 公開直前でライセンスを決めると、依存選定ミス（GPL混入など）や e-Stat 再配布規約違反を巻き戻せない。特に e-Stat は出典表記・加工明示義務がある。sample_case をダミーで作るのか、e-Stat 公開値を丸めるのかで配布条件が変わる。
- **提案**:
  - spec §6 に「ライセンス: Apache-2.0 または MIT（研究ユーザー向けは特許条項のある Apache-2.0 推奨）」を明記。
  - spec §7.1 と §20 に「`data/sample_case/` は完全合成ダミーとし、e-Stat 実データは同梱しない。e-Stat データ取得スクリプト（`scripts/fetch_estat.py`）のみを同梱し、ユーザー環境でダウンロードさせる」方針を記述。
  - DATASET.md に e-Stat 利用規約（出典表示義務）・加工の明示・再配布禁止の有無を書くタスクを Phase 1 に入れる。

### 【指摘3】harada 2024 の評価軸（ARD）が spec に位置付けられていない

- **現状**: spec §13.3 の privacy 評価に ARD が列挙されているが、harada 2024 論文の名前も参照も無い。
- **問題**: リポジトリ名に "harada-2024" を冠しているのに、spec 本文で harada 2024 の貢献が反映されていない。OSS ユーザーは「何の再現か」で信頼を測るため、論文→実装→評価メトリクスのマッピングが不可欠。
- **提案**: spec §5.3 を「Murata 2017 は生成側、Harada 2024 は評価側（有用性・秘匿性、ARD）の基準を与える」と明記し、§13 の各指標に出典を付ける。

## 中程度の指摘（Phase 1〜3中に整備）

### 【指摘4】CLI の入口 UX が長い

- **現状**: spec §17 の CLI は `uv run python -m synthetic_population.cli generate ...` と毎回30文字超。
- **問題**: OSS の初回体験で挫折率が上がる。`uvx` や `pipx` で一発起動できないと Quickstart が書きにくい。
- **提案**:
  - `pyproject.toml` の `[project.scripts]` に `synthpop-jp = "synthetic_population.cli:app"` を登録し、`uvx synthpop-jp generate --config ...` で動くようにすることを spec §17 に追記。
  - `synthpop-jp quickstart` サブコマンドで sample_case を使い10秒で合成人口を生成して `outputs/quickstart/` に吐くタスクを追加（Phase 2 の末尾で良い）。
  - `--config` 未指定時に同梱デフォルト config を使う仕様を spec §18 に明記。

### 【指摘5】拡張ポイント（plugin）の設計が曖昧

- **現状**: spec §22 に「追加データや追加評価器を差し込みやすい構成」とだけ書かれ、具体的な拡張手順がない。spec §9 のディレクトリ分離はあるが、外部パッケージからの注入方法は未定義。
- **問題**: 研究者は「自分の評価指標を足したい」「別の family_type を追加したい」が動機で来るが、内部コードを fork するしかない構造だと PR が集まらず死蔵する。
- **提案**: spec §9 と §14.2 に以下を追加。
  - `family_type` レジストリ: `register_family_type(name, template)` の公開API。
  - transition レジストリ: `register_transition(name, fn)`（age-change / age-swap 以外を追加可能にする）。
  - evaluator レジストリ: `pyproject.toml` の `[project.entry-points."synthpop_jp.evaluators"]` で外部パッケージからも登録可能。
  - CONTRIBUTING.md に「新 family_type を足す10行の例」「新評価器を足す20行の例」を記載。

### 【指摘6】config スキーマの契約が曖昧

- **現状**: spec §18 に config.yaml の例はあるが、JSON Schema / pydantic モデル定義は spec に無い。
- **問題**: OSS ユーザーが config を書き換えた際にエラーが不親切だと離脱する。研究者ほど「YAML の typo で数時間溶かす」に弱い。
- **提案**: spec §6.2 で `pydantic` を採用している点を活かし、`config.py` に `GenerateConfig`, `AnnealingConfig`, `ObjectiveConfig`, `ImproveConfig` の pydantic モデルを定義し、spec §18 にスキーマ表を載せる。`--validate-config` サブコマンドで CLI チェックだけ走れるようにする。

### 【指摘7】再現性メタデータの欠落

- **現状**: spec §19.3 で「seed 固定時の回帰テスト」があるが、Python バージョン / OS / lockfile の固定方針は未記載。
- **問題**: 1〜2年で `scikit-learn` や `scipy` の挙動差で数値が揺れ、回帰テストが破綻する。論文再現用リポジトリの信頼を一気に失う。
- **提案**:
  - spec §6.1 に「`uv.lock` をコミットし、CI はこの lock で再現」を明記。
  - spec §19 に「回帰テストの許容幅（例: best_score ±1%）」を定義。
  - `paper_results/` ディレクトリを設け、Phase 3 の実験1〜4（spec §15）の出力 CSV を固定 seed でコミットし、CI で差分チェック。

### 【指摘8】日本語公開統計テンプレートが未同梱

- **現状**: spec §7.1 で CSV の列定義はあるが、e-Stat / 国勢調査の「実際の列名・コード体系」との対応表がない。
- **問題**: 日本人ユーザーが真っ先にやる「e-Stat のダウンロード結果をそのまま食わせる」ができず、前処理で挫折する。これは synth-pop OSS で最も差別化できるポイント。
- **提案**: `data/templates/estat/` に e-Stat API レスポンスから spec §7.1 形式に変換する adapter（`from_estat_api.py`）を Phase 1 で入れる。`family_type_counts.csv` の `family_type` 9種（spec §8.1）と国勢調査「家族類型」の対応表（DATASET.md）を同梱。

## 軽微な指摘（公開前までに）

### 【指摘9】ドキュメント戦略

- **現状**: spec §20 成果物に README, spec.md, experiment_plan.md, assumptions.md しかなく、Quickstart / API reference / チュートリアル notebook が無い。
- **提案**:
  - `mkdocs-material` で静的サイト（日本語 primary / 英語 secondary）。GitHub Pages 公開。
  - `docs/tutorials/01_quickstart.ipynb`, `02_murata_reproduction.ipynb`, `03_custom_evaluator.ipynb` の3本を v0.2 までに。
  - spec.md の英訳は v1.0 タイミングで十分だが、README と Quickstart だけは v0.1 から英語版を用意（海外の synth-pop コミュニティに刺しに行くため）。

### 【指摘10】CI / コミュニティテンプレ

- **現状**: spec §19 にテスト種別はあるが、CI 設定・PR テンプレ・Issue テンプレの方針が無い。
- **提案**:
  - `.github/workflows/ci.yml`（pytest + ruff + mypy、3.11/3.12 マトリクス）、`release.yml`（tag → PyPI）。
  - ISSUE_TEMPLATE: bug / feature / new-family-type / new-evaluator の4種。
  - Discussions 有効化し、「自分の統計で動かない」相談を集約。
  - CODE_OF_CONDUCT.md は Contributor Covenant を採用。

### 【指摘11】比較表とベンチマーク

- **現状**: 上流OSS との差別化が spec に無い。
- **提案**: README に以下の比較表を置く。
  - synthpop (R): サンプル個票必須 ↔ 本実装: 集計表のみ
  - SDV / CTGAN: 表形式データ全般、GAN系 ↔ 本実装: 世帯構造を保存する SA 系
  - PopulationSim / ActivitySim: 旅客需要向け、IPF ベース ↔ 本実装: 目的関数カスタム可能な SA
  - 本実装の強み: 日本の国勢調査テンプレート / ARD 評価内蔵 / Murata 2017 再現。

### 【指摘12】引用・DOI

- **現状**: spec §20 に CITATION.cff なし。
- **提案**: v0.1 公開時に `CITATION.cff` を作り、Zenodo 連携で DOI を発行。v1.0 で論文 DOI と並記。

## 追加で必要と考えるタスク

- **タスクA: 命名と license 確定**（成果物: PyPI候補名、LICENSE, NOTICE, DATASET.md／Phase 0 = Phase 1 の前）
- **タスクB: e-Stat adapter と公開統計テンプレ**（成果物: `data/templates/estat/`, `scripts/fetch_estat.py`, DATASET.md ／Phase 1）
- **タスクC: plugin レジストリ設計**（成果物: `registry.py`, entry_points定義、CONTRIBUTING.md の拡張例／Phase 3）
- **タスクD: pydantic config スキーマと `--validate-config`**（成果物: `config.py` の型定義、JSON Schema 出力／Phase 1 末尾）
- **タスクE: Quickstart と mkdocs サイト**（成果物: README 英訳、`docs/tutorials/*.ipynb`、mkdocs.yml、GitHub Pages／Phase 4）
- **タスクF: CI / リリース基盤**（成果物: `.github/workflows/`, Issue/PR テンプレ、CODE_OF_CONDUCT, CHANGELOG, SemVer 方針／Phase 2）
- **タスクG: paper_results と Zenodo 連携**（成果物: `paper_results/`, `Makefile` で再現、CITATION.cff、Zenodo DOI／Phase 5〜v1.0）
- **タスクH: 比較表とベンチマーク記事**（成果物: README 比較表、Zenn/ブログ記事、学会ポスター、SDV との end-to-end 比較ベンチ／v0.2〜v1.0）

## OSS ロードマップ提案

- **v0.1 (Phase 2 完了時点)**: `uvx synthpop-jp quickstart` が10秒で動く。sample_case ダミー同梱。age-change のみ。README 日英。LICENSE, CITATION.cff, CI 済。PyPI に alpha 公開。
- **v0.2 (Phase 4 完了時点)**: age-swap / hybrid、ARD を含む評価、e-Stat adapter、mkdocs サイト、3本の notebook チュートリアル、SDV 比較表。
- **v0.3 (Phase 5 完了時点)**: 改善ループ（rule-based tuner）、複数 trial、比較レポート自動生成。plugin entry_points 公開。
- **v1.0 (論文公開と同時)**: Murata 2017 再現結果を `paper_results/` に固定、Zenodo DOI、CITATION.cff 更新、英語ドキュメント完備、Contributor Covenant、SemVer 宣言。

## Phase 順序への提案

spec §16 の Phase 1〜5 は技術順序として妥当だが、OSS 観点で以下を追加。

- **Phase 0（新設、1〜2日）**: 命名確定、LICENSE、pyproject.toml、CI skeleton、README 骨子、CITATION.cff の空ファイル。Phase 1 に入る前に「外形」を整える。
- **Phase 1 の末尾に config 検証と `quickstart` CLI を追加**（spec §17 へ）。「初回ユーザーが5分で動かせる」を Phase 1 完了条件にする。
- **Phase 3 と Phase 4 の間に plugin レジストリ**を入れる（評価器を追加する前に拡張点を固めるため）。
- **Phase 5 の後に v1.0 準備 Phase 6** を設け、paper_results 固定と Zenodo DOI 取得。

## 推奨する追加ファイル/構成

```
/
  LICENSE                  # Apache-2.0 推奨
  NOTICE                   # 依存ライブラリのクレジット
  README.md                # 日本語primary、英語セクション併記
  README.en.md             # v0.2以降
  CITATION.cff             # Zenodo 連携用
  CODE_OF_CONDUCT.md       # Contributor Covenant
  CONTRIBUTING.md          # 新 family_type / 評価器追加手順
  CHANGELOG.md             # Keep a Changelog 形式、SemVer
  DATASET.md               # e-Stat 利用規約、sample_case の由来
  pyproject.toml           # [project.scripts] に synthpop-jp を登録
  uv.lock                  # 再現性固定
  Makefile                 # make quickstart, make paper, make docs
  mkdocs.yml               # v0.2以降
  .github/
    workflows/ci.yml, release.yml
    ISSUE_TEMPLATE/{bug,feature,new-family-type,new-evaluator}.yml
    PULL_REQUEST_TEMPLATE.md
  data/
    sample_case/           # 完全ダミー
    templates/estat/       # 国勢調査列名マッピング
  scripts/
    fetch_estat.py         # e-Stat API で取得、再配布しない
  paper_results/           # Murata 再現と Harada 評価の固定出力
  docs/
    spec/spec.md (既存)
    tutorials/*.ipynb
    reviews/ (既存)
```

### 各ファイルの骨子メモ

- **README.md**: 1) プロジェクト一行説明（Murata 2017 再実装 + Harada 2024 評価）、2) 30秒 Quickstart（`uvx synthpop-jp quickstart`）、3) 入出力一覧、4) 比較表、5) 引用、6) ライセンス。最上部に論文参照と harada 2024 の関係を明示。
- **LICENSE**: Apache-2.0。特許条項が研究ユーザー安心材料。
- **CITATION.cff**: authors / version / doi / repository-code / preferred-citation（Murata 2017 と Harada 2024）。
- **CONTRIBUTING.md**: 開発環境セットアップ（`uv sync`）、pre-commit、ruff、mypy、テスト実行、新 family_type/evaluator の追加10〜20行例、PR の branch 命名（`feature-<issue>-<keyword>`、user の CLAUDE.md の worktree ルールと整合）。
- **DATASET.md**: e-Stat 利用規約、出典表示義務、sample_case の生成方法（`scripts/generate_sample_case.py` で seed 固定）、再配布禁止の実データを含めない方針。
- **CHANGELOG.md**: Keep a Changelog + SemVer。v0.x の間は破壊的変更を許容する旨を明記。
