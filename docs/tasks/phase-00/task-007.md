# task-007: src/synthpop_jp/ ディレクトリ骨格と Protocol 定義

## 目的

Phase 1 以降の実装が入る空のパッケージ構造と、3 者レビューで合意した **Protocol 抽象**（内部実装と拡張点の境界）を `typing.Protocol` で先置きする。実体は空・`...` で可。

## 前提・依存

- task-004 で pyproject.toml と pyright strict が通る状態。
- ADR-0001（内部表現は NumPy 並列配列 + 差分更新）を task-008 で先に commit。
- Protocol と並列配列表現は層分離（Protocol は境界、並列配列は `optimize/` 内）。

## 成果物

### a. ディレクトリ構造

```
src/synthpop_jp/
  __init__.py
  cli.py                  # typer app, サブコマンド未実装（Phase 1 で quickstart）
  config.py               # pydantic-settings ベース、GenerateConfig 等
  registry.py             # register_family_type / register_transition / register_evaluator
  io/
    __init__.py
    loaders.py            # Phase 1
    writers.py            # Phase 1
  domain/
    __init__.py
    protocols.py          # 本タスクで定義
    household.py          # Phase 1
    person.py             # Phase 1
    statistics.py         # Phase 2
    distance.py           # Phase 4
  init/
    __init__.py
    household_sampler.py  # Phase 1
    initial_population.py # Phase 1
  optimize/
    __init__.py
    state.py              # PopulationArrays dataclass（本タスクで骨子のみ）
    objective.py          # Phase 2
    annealing.py          # Phase 2
    transitions.py        # Phase 2〜3a
    cooling.py            # Phase 2
  evaluate/
    __init__.py
    aggregate_metrics.py  # Phase 3.5
    utility_metrics.py    # Phase 4
    privacy_metrics.py    # Phase 4
    attribute_inference.py # Phase 3.5 (CAP/TCAP)
    rare_cell_metrics.py  # Phase 3.5
    downstream_tasks.py   # Phase 4
  improve/
    __init__.py
    tuner.py              # Phase 5
    strategy.py           # Phase 5
  experiments/
    __init__.py
    runner.py             # Phase 3b
    comparison.py         # Phase 3b
    pareto.py             # Phase 5
```

### b. `domain/protocols.py`

```python
from typing import Protocol, runtime_checkable
from numpy.random import Generator
import numpy as np

# Forward declaration: PopulationArrays は optimize/state.py
# ここでは型エイリアスとして np.ndarray を扱う抽象で可


@runtime_checkable
class Transition(Protocol):
    name: str
    def propose(self, state, rng: Generator) -> "Proposal": ...
    def apply(self, state, proposal: "Proposal") -> None: ...
    def revert(self, state, proposal: "Proposal") -> None: ...


@runtime_checkable
class CoolingSchedule(Protocol):
    def temperature(self, iter: int) -> float: ...


@runtime_checkable
class Evaluator(Protocol):
    name: str
    def evaluate(self, pop) -> dict[str, float]: ...


@runtime_checkable
class Distribution(Protocol):
    """将来の DP 拡張に備えた noisy target の抽象。現段階は決定的 target のみ実装。"""
    def mean(self) -> np.ndarray: ...
    def sample(self, rng: Generator) -> np.ndarray: ...


@runtime_checkable
class PrivacyMetric(Protocol):
    name: str
    layer: str  # "proxy" | "attribute_inference" | "mia"
    def evaluate(self, synthetic, holdout) -> dict[str, float]: ...
```

`Proposal` は `optimize/state.py` で dataclass として定義（age, index, before, after などを持つ、詳細は Phase 2）。

### c. `optimize/state.py`

```python
from dataclasses import dataclass
import numpy as np

@dataclass
class PopulationArrays:
    age: np.ndarray           # int16, shape=(n_persons,)
    sex: np.ndarray           # int8 (0=M,1=F)
    role: np.ndarray          # int8 (enum)
    household_id: np.ndarray  # int32
    family_type: np.ndarray   # int8 (enum)

@dataclass
class Proposal:
    transition: str
    indices: np.ndarray       # 変更対象 person の index
    before: np.ndarray        # 変更前の値
    after: np.ndarray         # 変更後の値
```

### d. `registry.py`

`register_family_type / register_transition / register_evaluator` の関数骨子と、`pyproject.toml` の entry_points からの自動読込ヘルパ（実装は Phase 3）。

### e. `cli.py`

```python
import typer
app = typer.Typer(help="synthpop-jp: synthetic population generator")

@app.command()
def quickstart() -> None:
    """Phase 1 で実装。"""
    raise NotImplementedError

@app.command()
def generate(config: str = "configs/base.yaml") -> None:
    raise NotImplementedError

@app.command()
def evaluate(run_dir: str) -> None:
    raise NotImplementedError

@app.command()
def improve(config: str = "configs/base.yaml", trials: int = 10) -> None:
    raise NotImplementedError

@app.command()
def compare(experiment: str) -> None:
    raise NotImplementedError

@app.command("validate-config")
def validate_config(config: str) -> None:
    raise NotImplementedError
```

### f. `tests/` 骨格

```
tests/
  unit/
  integration/
  property/
  regression/
  conftest.py            # 空
  test_imports.py        # パッケージが import できることだけを確認
```

## 受け入れ基準

- `uv run pyright` が strict で緑。
- `uv run pytest tests/test_imports.py` が `from synthpop_jp import *` で例外を出さない。
- `synthpop-jp --help` が 6 サブコマンドを表示する（全て NotImplementedError）。
- `isinstance(obj, Transition)` などの `runtime_checkable` が動作するサンプルテスト 1 本を `tests/unit/test_protocols.py` に追加。

## 推定規模

M（半日〜1 日）。

## 参照

- `docs/reviews/review-python.md` 指摘 1, 5, 6
- `docs/reviews/review-privacy.md` S7（Distribution, PrivacyMetric の将来拡張）
- `docs/reviews/review-oss.md` 指摘 5（plugin レジストリ）
- `docs/reviews/action-plan.md` §2E / §3.2
