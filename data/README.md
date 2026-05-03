# data/

`synthpop-jp` の入力データを置きます。**実データ（e-Stat 由来の集計表）はリポジトリに含めません**。同梱されているのは合成ダミーのみです。

## 中身

- [`sample_case/`](sample_case/) — 同梱の合成ダミー。`scripts/generate_sample_case.py` で seed 固定で生成された 7 本の CSV。`synthpop-jp quickstart` がこれを読み込む

## データの取り扱いポリシー

e-Stat 利用規約・統計法 §44・出典表示義務などの全ポリシーは [`docs/DATASET.md`](../docs/DATASET.md) に集約しています。実データを使う場合は必ず読んでください。

## 実データを取り込む

e-Stat からの集計表取り込みは `scripts/fetch_estat.py`（[Issue #103](https://github.com/gghatano/synth-pop-harada-2024/issues/103) で対応中）で実行する想定です。取得したデータは `data/<dataset_slug>/` 以下に置き、`docs/DATASET.md` に出典を追記してください。

## CSV のスキーマ

各 CSV の列・型・単位・欠損規則は [`docs/spec/data_contract.md`](../docs/spec/data_contract.md) で定義されています。pydantic ローダ (`src/synthpop_jp/io/loaders.py`) はこの契約に従って読み込み、不正な行は行番号付きでエラーを出します。
