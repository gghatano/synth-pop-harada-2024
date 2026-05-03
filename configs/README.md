# configs/

`synthpop-jp` の各コマンドが読み込む YAML 設定ファイルを置きます。

## 中身

| ファイル | 役割 |
|---|---|
| `base.yaml` | `synthpop-jp quickstart` / `generate` のデフォルト設定。`data/sample_case/` を入力として `outputs/quickstart/` に出力する。SA パラメータ・objective モード（`minimal` / `extended` / `strict_extended`）・遷移種別の既定値を含む |
| `family_type_mapping.yaml` | 9 種の family_type を 3 グループに分類する対応表（`docs/spec/spec.md` §8.1 に対応）。`children_count_dist.csv` など group 単位の統計を解釈するときに使う |

## 使い方

```bash
# デフォルト設定で動かす
uv run synthpop-jp quickstart

# 設定ファイルを差し替えて動かす
uv run synthpop-jp generate --config configs/base.yaml

# 設定ファイルの妥当性を事前チェック
uv run synthpop-jp validate-config configs/base.yaml
```

## 新しい設定を追加する

実験用の設定は `configs/<実験slug>.yaml` として置いてください。複数 config × n seed の比較は `synthpop-jp compare` で実行できます。スキーマは `src/synthpop_jp/config.py` の pydantic モデル、項目の意味は `docs/spec/spec.md` §18 を参照してください。
