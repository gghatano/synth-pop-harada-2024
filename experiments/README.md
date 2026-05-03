# experiments/

仮説を立てて何かを **実測した結果** を、再現可能な形で残すディレクトリです。

論文の検証実験リポジトリとして「どの主張がどの実験で裏付けられているか」を後から追えるよう、各実験は固定の slug ディレクトリに閉じ込めます。

## ディレクトリ構成

```
experiments/
└── YYYY-MM-DD-<slug>/
    ├── INPUT.md     # 何を確かめたいか / 仮説 / 入力条件 / seed
    ├── WEIGHT.md    # light / heavy（重実験フラグ、`make pm` がこれを読む）
    ├── run.py       # 再現用スクリプト
    ├── config.yaml  # 必要なら設定ファイル
    ├── outputs/     # 中間成果物（gitignore 対象になることもある）
    ├── report.md    # 結果まとめ（数値・グラフ・解釈）
    └── report.html  # HTML 化（plotly inline、self-contained ≤ 1MB）
```

詳細なルールは [`docs/rules/experiment-management.md`](../docs/rules/experiment-management.md) と [`docs/rules/html-reporting.md`](../docs/rules/html-reporting.md) を参照してください。

## 既存の実験

| 日付 / slug | 何を確かめたか | 主な数値 |
|---|---|---|
| [`2026-04-25-quickstart-sample-case/`](2026-04-25-quickstart-sample-case/) | 初期生成（100 世帯 / 266 人）と HTML レポートの動作確認 | 約 1.1 秒で生成、HTML ≤ 1MB |
| [`2026-04-29-sa-memory-profile/`](2026-04-29-sa-memory-profile/) | SA の RAM 消費を 1k〜100k 世帯で実測 | 100k 世帯でも peak RSS 358MB（25.8GB の 1.4%） |
| [`2026-04-30-9-family-types-coverage/`](2026-04-30-9-family-types-coverage/) | 9 family types すべてが SA 経路を通ることを seed×5 で確認 | 全 9 種で family_type 構成比が維持される |

## 新しい実験を追加する

1. `experiments/YYYY-MM-DD-<slug>/` を切る（slug は短く・意味が伝わるもの）
2. `INPUT.md` に仮説と入力条件、seed、コミット SHA を書く
3. `WEIGHT.md` に `light` または `heavy` を 1 行（N ≥ 100k 世帯は heavy）
4. `run.py` で実行できる状態にする
5. `report.md` に結果と解釈を書き、HTML レポートが必要なら `report.html` も置く
6. 失敗した実験も捨てない（仮説の振り返りに使う）

実験コミットには対応する Issue 番号を含めると、後から実装と実験を結びつけやすくなります。
