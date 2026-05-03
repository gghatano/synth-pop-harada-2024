"""Quickstart 実験の再実行スクリプト（Issue #115 audit 互換のためのラッパ）.

実際の実装は ``synthpop-jp quickstart`` CLI 側にある。本ファイルは
``scripts/audit_experiments.py`` が要求する ``run.py`` の存在条件を満たし、
かつ「再実行 1 コマンド」の窓口を提供するためのラッパ。
"""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    """``uv run synthpop-jp quickstart`` を呼び出す."""
    return subprocess.run(
        ["uv", "run", "synthpop-jp", "quickstart"],
        check=False,
    ).returncode


if __name__ == "__main__":
    sys.exit(main())
