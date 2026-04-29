# 2026-04-29 セッション引き継ぎ — Phase 3 自律進行チェックポイント

このドキュメントは、2026-04-29 の長時間セッションで進めた Phase 3 サブ Issue 3 件の状態をまとめ、
次セッションが Phase 3 の続きを引き取るために必要な情報を 1 枚に集約したものです。

- 対象 develop SHA: `03c3158` (PR #62 merged 直後)
- 本体テスト: 450 passed / 10 skipped
- 関連 Issue: closed = #51 / #52 / #53 / #57 / #59 / #61、open = #46 / #47 / #48（Phase 2 別軌道）

---

## 1. 非技術者向け要約

合成人口（統計に合わせて作る人工データ）を「作る」「評価する」「整える」の 3 軸のうち、
このセッションでは **作る軸の拡張**（age-swap 遷移）と **評価する軸の最初の 2 個の評価器** を実装しました。

具体的には、`synthpop-jp evaluate` という 1 コマンドで、合成人口の品質を 6 つの統計の誤差と
「個人特定リスク」の 2 軸で測れるようになりました。出力は `metrics.json` に書き出されるため、
非エンジニアもファイルを開いて数値を確認できます。

次セッションは、これと同じパターンで残りの評価器（属性推論・近接性指標）を増やしていく方針です。

---

## 2. このセッションで完了した PR (合計 6 件)

| # | PR | 内容 | merge SHA |
|---|---|---|---|
| #51 | #54 | SA 実行ピーク RAM の実測 (heavy 実験基盤) | c3e4478 |
| #52 | #55 | 重実験 WEIGHT.md ルールと `make pm` 表示 | 7dfdf74 |
| #53 | #56 | trace/resume/HTML メモリ監査 + persons.copy 排除 | dc78138 |
| #57 | #58 | Phase 3a: age-swap 遷移 (Murata §12.2B) | fd8deae |
| #59 | #60 | Phase 3.5: AggregateStatL1Evaluator + evaluate CLI | 7873f52 |
| #61 | #62 | Phase 3.5: RareCellEvaluator | 03c3158 |

特に #57 以降が Phase 3 着手分です。

---

## 3. Phase 3 の進捗マップ

`docs/reviews/action-plan.md` §3.5–3.7 の作業をチェックリスト化:

### Phase 3a (Murata 拡張)

- [x] **age-swap 遷移** (#57 / PR #58)
- [ ] hybrid 遷移 (`p_change` / `p_swap` スケジュール、§12.2C)
- [ ] family_type × role × sex 分布の年齢サンプリング
- [ ] extended objective (21 統計、§11.3、原論文式(3))
- [ ] 初期生成の 21 統計誤差 0 化 (Priv S2)

### Phase 3.5 (評価器骨格)

- [x] Evaluator Protocol skeleton (Phase 0 で既に存在)
- [x] **統計別 L1 誤差レポータ** (#59 / PR #60、AggregateStatL1Evaluator)
- [x] **rare cell 監視メトリクス** (#61 / PR #62、RareCellEvaluator)
- [ ] CAP 先行実装 (`evaluate/attribute_inference.py`、Priv 指摘3)
- [ ] Table 13 形式の `report.md` 自動追記
- [ ] 評価 plugin entry_points テスト（評価器 ≥ 2 個揃ったので可能）

### Phase 3b (比較 runner)

- [ ] `synthpop-jp compare` サブコマンド
- [ ] seed runner (n=10–30) + Welch's t / Holm 補正
- [ ] bootstrap CI

---

## 4. 次セッションの推奨 Issue (優先順)

### 優先 A — 1 PR で完結、即着手可

**A1. CAP/TCAP 評価器** (`evaluate/attribute_inference.py`)
- スコープ: ~300 行、既存の RareCellEvaluator パターンを踏襲
- 価値: 秘匿性 baseline の 2 つ目。`docs/spec/metrics.md` §5.2 に仕様
- 前提: なし（既に揃っている）

**A2. hybrid 遷移** (`optimize/transitions.py::HybridTransition`)
- スコープ: ~150 行、AgeChange + AgeSwap を internal に持って propose を委譲
- 価値: Phase 3a の SA 比較実験（#15.1）の準備
- 前提: なし

### 優先 B — 中規模、Phase 3a の前提条件

**B1. extended objective (21 統計)** (`optimize/objective.py`)
- スコープ: ~600 行、`build_objective_stats` を 5→21 拡張
- 価値: AggregateStatL1Evaluator も自動的に 21 統計対応に拡張される
- 前提: spec §11.3 の式定義を再確認

### 優先 C — 後回し可

**C1. Table 13 形式の report.md 自動追記**
- HTML 化との関係を整理してから着手するのが望ましい

**C2. evaluate plugin entry_points テスト**
- 評価器が 3 個以上になったら入れたい

---

## 5. アーキテクチャ重要点 (次の Issue で参照)

### evaluate CLI の構造

```python
# src/synthpop_jp/cli.py の evaluate サブコマンド
arrays = reconstruct_population_arrays_from_persons_csv(persons_csv)
metrics = {
    **AggregateStatL1Evaluator(...).evaluate(arrays),
    **RareCellEvaluator().evaluate(arrays),
}
# metrics.json に追記
```

新しい Evaluator を追加するときは、ここに 1 行加えるだけ。

### Evaluator Protocol

```python
# src/synthpop_jp/domain/protocols.py
class Evaluator(Protocol):
    name: str
    def evaluate(self, pop: PopulationArrays) -> dict[str, float]: ...
```

返り値の dict キー命名規則: `<name>.<metric>` または `<name>.<metric>.<sub_attribute>`

### Population I/O

- 生成: `synthpop-jp generate --config foo.yaml` → `output_dir/synthetic_persons.csv`
- 再構築: `io/synthesized.py::reconstruct_population_arrays_from_persons_csv(persons_csv)`
- registry の lazy 登録（CSV 内の登場順）

### 重実験ルール (Issue #52)

- `experiments/<dir>/WEIGHT.md` に `light` または `heavy` を 1 行
- N >= 100k 世帯 = heavy
- `make pm` で `⚠ heavy` を表示
- heavy worktree が active な間は他 Agent 起動禁止（`.claude/skills/multi_agent_orchestration.md` §並列起動の判断）

---

## 6. アクティブな運用状態

### Active worktrees (2026-04-29 23:30 JST 時点)

| worktree | branch | PR | コメント |
|---|---|---|---|
| feature-46-commit-cadence | feature/46-commit-cadence | #49 (Draft) | Phase 2 別軌道 |
| feature-47-make-ci | feature/47-make-ci | なし | Phase 2 別軌道 |
| feature-48-merge-pr-helper | feature/48-merge-pr-helper | #50 (Draft) | Phase 2 別軌道 |
| feature-63-phase3-handoff | feature/63-phase3-handoff | this PR | このドキュメントの作成 |

### Scheduled remote routine

- `trig_011U4fipzbHCMzUEQ8a9iug1`: WEIGHT.md cleanup check (2026-05-13T00:00:00Z, 1 回限り)

---

## 7. ユーザー応答スタイルのメモ

ユーザーは「自律的に進めて / OK / まかせます」のような短承認で長作業を委譲する。
2026-04-29 セッションでは「自律的に進めて」の指示で 6 PR を 1 セッションで merge した。

次セッションでも同様のスタイルが期待される。詳細は auto-memory `user_autonomy_style.md` 参照。

---

## 8. このドキュメント自身の取り扱い

- 永続性: 今後の handoff doc も `docs/reports/YYYY-MM-DD-phaseN-handoff.md` 形式で残す
- 再生成: 各セッション末に新規作成（このドキュメントを更新するのではない）
- 索引: auto-memory `phase3_progress.md` がこの doc を参照する

## 関連ドキュメント

- `docs/reviews/action-plan.md` — Phase 全体の作業計画
- `docs/spec/spec.md` §11.3, §11.5, §12.2, §13 — 残作業の仕様参照
- `docs/spec/metrics.md` — 評価器の出力指標定義
- `experiments/2026-04-29-sa-memory-profile/report.md` — SA メモリ実測値（#51）
- auto-memory: `phase3_progress.md`、`user_autonomy_style.md`、`active_routines.md`
