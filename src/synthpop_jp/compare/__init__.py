"""Compare runner と統計検定 (Phase 3b, Issue #80).

`synthpop-jp compare` サブコマンドのバックエンド。複数 config × 複数 seed の
SA を実行し、メトリクスを統計的に比較する。

提供するもの
------------
- ``compare.runner``: seed sweep の実行
- ``compare.stats``: Welch's t / Wilcoxon signed-rank / Holm 補正
- ``compare.report``: compare.json / compare.md 出力
"""
