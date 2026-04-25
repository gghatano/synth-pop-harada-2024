# Phase 2 ベンチマーク結果

実施: 2026-04-25, develop @ `1141145`（Issue #43 merged 直後）
測定マシン: macOS / Apple Silicon、`uv run pytest -m benchmark --benchmark-only`

## 1. 結果サマリ

| ベンチ | median | min | max | 目標 | 結果 |
|---|---|---|---|---|---|
| `ObjectiveState.propose_change`（副作用なし） | 1.5 μs | 1.3 μs | 6.0 μs | < 100 μs | ✅ 67 倍速い |
| `ObjectiveState.propose_change`（apply 後の状態確認込み） | 1.6 μs | 1.3 μs | 54.3 μs | < 100 μs | ✅ |
| `AgeChangeTransition.propose` | 7.5 μs | 7.1 μs | 65.4 μs | < 10 μs | ✅ |
| SA 1000 世帯 × 1 万反復（smoke 用） | 402 ms | - | - | < 5 s | ✅ 12 倍余裕 |
| **SA 1000 世帯 × 20 万反復（Phase 2 Exit）** | **5.2 s** | 4.1 s | 5.5 s | **< 30 s** | ✅ **5.8 倍余裕** |
| SA score improves（収束 sanity） | 5.3 s | - | - | best < initial | ✅ |

**Phase 2 性能ゲート（action-plan §3.4）達成**: 1000 世帯 × 20 万反復が median 5.2 秒で 30 秒目標を 5.8 倍上回る性能で完走。

## 2. 解釈

差分更新の効果が顕著に現れている。
全再計算なら 1 反復に O(N) かかるところを O(1) で済ませているため、
20 万反復 × 1.5 μs/反復 = 0.3 秒分の純粋計算 + Metropolis 受理判定や rng のオーバーヘッドを足しても 5 秒台で済む。

`AgeChangeTransition.propose` の 7.5 μs は role 別年齢分布からのサンプリング + ハード制約 retry を含むため propose_change より大きいが、SA 全体のホットパスとしては十分小さい。

## 3. CI 運用

- **CI（GitHub Actions）**: smoke 版（1000 世帯 × 1 万反復 ≤ 5 秒）のみを毎 PR で走らせる。本格 20 万反復は時間と環境揺れで CI には載せない
- **ローカル本格計測**: `make bench` または `uv run pytest -m benchmark --benchmark-only`。リリース前と性能 regression 疑いがある時に手動実行
- **既定スキップ**: `pyproject.toml` の `addopts = "--benchmark-skip"` で通常 `uv run pytest` では benchmark が skip される

## 4. 制約と今後

- 本計測は 1 マシン（macOS / Apple Silicon）。Linux x86_64（CI 環境）では数値が変わる可能性あり、CI smoke で粗く検証
- 1000 世帯（266 人）規模。実用的な 10 万人規模での挙動は Phase 3a 以降で再計測する想定
- 並列化（`joblib` / `concurrent.futures`）は本 Issue 範囲外。マルチ seed 比較を回す Phase 3b で別途検討

## 5. 関連

- `docs/reviews/action-plan.md` §3.4 Phase 2 Exit 条件
- `docs/reviews/action-plan.md` §5 リスク表 1 行目（SA 性能未達リスク）
- Issue #33（本ベンチの導入）
- `tests/benchmarks/`（テスト本体）
