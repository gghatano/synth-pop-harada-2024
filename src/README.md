# src/

Python ソースの src layout ルートです。本リポジトリのパッケージは [`synthpop_jp/`](synthpop_jp/) 1 つだけ。

## なぜ src layout か

- import の曖昧さ（カレントディレクトリのコードと install 済みパッケージの取り違え）を防ぐため
- `uv sync` でインストールしたコードと、エディタが見ているコードを同じものに揃えるため

## パッケージ構成

中身は [`synthpop_jp/README.md`](synthpop_jp/README.md) を参照してください。
