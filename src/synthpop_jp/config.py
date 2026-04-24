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
from pydantic import BaseModel, ConfigDict, field_validator


class AnnealingConfig(BaseModel):
    """SA（シミュレーテッドアニーリング）の実行パラメータ設定.

    ``Settings.annealing`` フィールドとして組み込む。

    Attributes
    ----------
    T0 : float
        初期温度。ExponentialCooling に渡す。デフォルト 100.0。
    alpha : float
        冷却率 (0 < alpha <= 1.0)。デフォルト 0.999。
    max_iters : int
        最大反復回数。0 以下は無制限（evals_per_agent で制御する）。
        デフォルト 1_000_000。
    evals_per_agent : int
        1 person あたりの評価回数上限。0 以下は無効。
        停止条件: iter >= evals_per_agent * n_persons。
        デフォルト 1000。
    target_threshold : float
        この値以下になったら停止する（0.0 は無効）。デフォルト 0.0。
    patience : int
        best_score が改善しない反復数の上限。0 は無効。デフォルト 0。
    """

    model_config = ConfigDict(extra="forbid")

    T0: float = 100.0
    alpha: float = 0.999
    max_iters: int = 1_000_000
    evals_per_agent: int = 1000
    target_threshold: float = 0.0
    patience: int = 0

    @field_validator("T0")
    @classmethod
    def t0_positive(cls, v: float) -> float:
        """T0 > 0 を検証する."""
        if v <= 0.0:
            msg = f"T0 は正の実数でなければなりません（T0={v}）"
            raise ValueError(msg)
        return v

    @field_validator("alpha")
    @classmethod
    def alpha_range(cls, v: float) -> float:
        """Alpha が (0, 1] の範囲内か検証する."""
        if v <= 0.0 or v > 1.0:
            msg = f"alpha は (0, 1] の範囲でなければなりません（alpha={v}）"
            raise ValueError(msg)
        return v


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
    annealing: AnnealingConfig = AnnealingConfig()

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
