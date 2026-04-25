"""SA 収束過程トレース — Issue #31.

SA ループの各反復記録（trace.jsonl）を書き出し・読み込みするモジュール。

提供するもの:
- ``TraceEvent``: 1 反復分のデータを保持する pydantic モデル
- ``TraceWriter``: trace.jsonl へ 1 行ずつ追記するコンテキストマネージャ
- ``read_trace(path)``: trace.jsonl を ``pandas.DataFrame`` に変換するヘルパー

trace.jsonl のスキーマ（1 行 = 1 JSON object）::

    {"iter": int, "temperature": float, "current_score": float,
     "best_score": float, "accepted": bool, "delta": float,
     "timestamp": str (ISO 8601)}

使い方::

    from pathlib import Path
    from synthpop_jp.optimize.trace import TraceEvent, TraceWriter, read_trace

    with TraceWriter(Path("outputs/run/trace.jsonl")) as writer:
        writer.write(
            TraceEvent(
                iter=0,
                temperature=100.0,
                current_score=500.0,
                best_score=500.0,
                accepted=True,
                delta=-10.0,
                timestamp="2026-04-24T00:00:00Z",
            )
        )

    df = read_trace(Path("outputs/run/trace.jsonl"))
    print(df[["iter", "best_score"]].head())
"""

from __future__ import annotations

import io
import types
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    import pandas as pd


# ---------------------------------------------------------------------------
# TraceEvent — 1 反復分のデータ
# ---------------------------------------------------------------------------


class TraceEvent(BaseModel):
    """SA 1 反復分のトレースデータ.

    Attributes
    ----------
    iter : int
        反復番号（0-indexed）。
    temperature : float
        その反復の SA 温度。
    current_score : float
        受理後の現在スコア（最後に受理された遷移後の値）。
    best_score : float
        これまでの最良スコア。
    accepted : bool
        この反復で遷移が受理されたか。
    delta : float
        スコア差分（new_score - old_score）。
    timestamp : str
        記録時刻（ISO 8601 形式、例: "2026-04-24T00:00:00Z"）。
    """

    model_config = ConfigDict(frozen=True)

    iter: int
    temperature: float
    current_score: float
    best_score: float
    accepted: bool
    delta: float
    timestamp: str


# ---------------------------------------------------------------------------
# TraceWriter — trace.jsonl への追記
# ---------------------------------------------------------------------------


class TraceWriter:
    """trace.jsonl へ 1 行ずつ追記するコンテキストマネージャ.

    コンテキストマネージャ（``with`` 文）として使うことでファイルを安全に閉じる。

    Parameters
    ----------
    path : Path
        書き込み先のファイルパス。親ディレクトリは自動作成される。

    Examples
    --------
    >>> from pathlib import Path
    >>> from synthpop_jp.optimize.trace import TraceEvent, TraceWriter
    >>> with TraceWriter(Path("trace.jsonl")) as writer:  # doctest: +SKIP
    ...     writer.write(TraceEvent(...))
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._file: io.TextIOWrapper | None = None

    def __enter__(self) -> TraceWriter:
        """ファイルを開いて書き込み準備をする."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self._path.open("a", encoding="utf-8")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        """ファイルを閉じる."""
        if self._file is not None:
            self._file.close()
            self._file = None

    def write(self, event: TraceEvent) -> None:
        """TraceEvent を 1 行 JSON として追記する.

        Parameters
        ----------
        event : TraceEvent
            書き込むトレースイベント。

        Raises
        ------
        RuntimeError
            コンテキストマネージャの外で呼ばれた場合。
        """
        if self._file is None:
            msg = "TraceWriter は `with` 文で使ってください"
            raise RuntimeError(msg)
        self._file.write(event.model_dump_json() + "\n")


# ---------------------------------------------------------------------------
# read_trace — trace.jsonl を DataFrame に変換
# ---------------------------------------------------------------------------


def read_trace(path: Path) -> pd.DataFrame:
    """trace.jsonl を読み込んで pandas DataFrame に変換する.

    Parameters
    ----------
    path : Path
        読み込む trace.jsonl のパス。

    Returns
    -------
    pd.DataFrame
        各行が 1 TraceEvent に対応する DataFrame。
        カラム: iter, temperature, current_score, best_score, accepted, delta, timestamp。

    Raises
    ------
    FileNotFoundError
        指定されたパスにファイルが存在しない場合。
    """
    import json

    import pandas as pd

    records: list[dict[str, object]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    return pd.DataFrame(records)
