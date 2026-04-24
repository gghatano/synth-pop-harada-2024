"""設定モデル — pydantic v2 ベースの CLI 設定.

``Settings`` は ``synthpop-jp`` CLI が使う実行設定をまとめる pydantic モデルです。
YAML ファイルから ``Settings.from_yaml(path)`` で読み込み、
``model_validate`` で型・値域のバリデーションを行います。

使い方::

    from pathlib import Path
    from synthpop_jp.config import Settings

    settings = Settings.from_yaml(Path("configs/base.yaml"))
    print(settings.seed)  # 42
    print(settings.input_dir)  # Path("data/sample_case")

設計方針
--------
- ``extra="forbid"`` で未定義キーを禁止する（spec §18）。
- ``input_dir`` / ``output_dir`` は ``Path`` 型で受け取る。
- フィールドのデフォルト値は ``configs/base.yaml`` と一致させる。
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict


class Settings(BaseModel):
    """CLI 全体の実行設定をまとめる pydantic モデル.

    Attributes
    ----------
    seed : int
        乱数の根シード。``SeedRegistry(root=seed)`` に渡す。デフォルト 42。
    input_dir : Path
        入力 CSV が置かれたディレクトリ。
    output_dir : Path
        出力先ディレクトリ。実行時に自動作成される。
    family_type_mapping : Path | None
        ``family_type_mapping.yaml`` のパス。省略時は ``configs/family_type_mapping.yaml``
        を自動検索する。
    """

    model_config = ConfigDict(extra="forbid")

    seed: int = 42
    input_dir: Path
    output_dir: Path
    family_type_mapping: Path | None = None

    @classmethod
    def from_yaml(cls, path: Path) -> Settings:
        """YAML ファイルから Settings を読み込む.

        Parameters
        ----------
        path : Path
            YAML 設定ファイルのパス。

        Returns
        -------
        Settings
            バリデーション済みの設定オブジェクト。

        Raises
        ------
        FileNotFoundError
            指定されたパスにファイルが存在しない場合。
        pydantic.ValidationError
            型・値域のバリデーションに失敗した場合。
        """
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls.model_validate(data)
