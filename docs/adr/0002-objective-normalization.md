# ADR-0002: 目的関数は 2 モード（原論文準拠 / 研究拡張）

- **Status**: Accepted
- **Date**: 2026-04-23

## Context

`docs/spec/spec.md` 旧版 §11.4 は目的関数を次の式で書いていた。

```text
objective = Σ_s Σ_j weight_s * abs(observed[s, j] - target[s, j])
```

この式には 2 つの問題がある。

1. **原論文との不整合**（`docs/reviews/review-privacy.md` 指摘 1）: Murata 2017 の式(1) は `f(A) = Σ_s Σ_j |c_{sj}(A) - Round(r_{sj} · m_{sj}(A))|` であり、21 統計拡張の式(3) は `f'(A) = Σ_s Σ_j |c_{sj}(A) - R_{sj}|`（`R_{sj}` は率ではなく実数値の実統計）である。原論文に `weight_s` は存在しない。`weight_s` を混ぜた式のまま「Murata 再現」を主張すると、再現性の根拠が弱くなる。
2. **統計間スケール不一致**（`docs/reviews/review-python.md` 指摘 4）: demographic pyramid（200 セル）と couple_gap（40 セル）を同じ L1 和で合算すると、セル数の多い統計が支配する。生の L1 では weight 調整が数日分の迷路になる。

両方の指摘を同時に満たすには、1 つの目的関数で頑張るのではなく、**2 モードに分離**するのが素直である。

## Decision

目的関数を次の 2 モードで併記する。config の `objective.mode` で切り替える。

### モード A: 原論文準拠モード（`mode: paper`）

Murata 2017 の式(1) / 式(3) に忠実な実装。

9 統計版（式(1)）:

```text
f(A) = Σ_s Σ_j | c_{sj}(A) - Round( r_{sj} · m_{sj}(A) ) |
```

21 統計版（式(3)）:

```text
f'(A) = Σ_s Σ_j | c_{sj}(A) - R_{sj} |
```

- `weight_s` は **使わない**
- `Round(r_{sj} · m_{sj}(A))` は **動的ターゲット**（生成集団側の分母 `m_{sj}(A)` に依存）であり、target を静的定数として実装する誤実装を防ぐためにこの点を spec §11.4 で明記した
- **§15.1 の実験 1（Murata 再現）は本モードのみで実施する**

### モード B: 研究拡張モード（`mode: research_extended`）

セル数正規化 + 統計間重みによる、実用チューニング向けの拡張。

```text
loss_s    = (1 / |cells_s|) * Σ_j | observed_rate[s, j] - target_rate[s, j] |
objective = Σ_s weight_s * loss_s
```

- `observed_rate` は合成集団の count を人口総数で割った率
- `weight_s` は §18 の `objective.weights` と対応し、**統計間の相対重要度** として解釈する
- セル数正規化により demographic pyramid と couple_gap が同スケールで合算される
- エントロピー正則化 `objective.entropy_regularization` オプションも本モードで有効（§11.6）

### 評価レポートの扱い

- `metrics.json` には `best_score_paper` と `best_score_research` を**両方**記録する
- `report.md` も両方を併記し、Murata 再現性と実用チューニングの両面が読めるようにする

## Consequences

### 肯定的な結果

- **Murata 再現性が担保される**: 式(1) / 式(3) を正しく実装できていることが実験 1 の結果で示される
- **実用チューニングが可能**: 研究拡張モードで重みを振り、統計整合性・有用性・秘匿性の多目的バランスを取れる
- **読者にとって透明**: どちらの主張をしているかが config の `mode` で明示される

### 否定的な結果

- **コード上は 2 実装が並走する**: `objective.py` が if/else で分岐するか、Protocol で差し替える形になる。`domain/protocols.py` の `Objective` Protocol で抽象化する予定
- **テスト工数が増える**: 両モードで決定性テスト・property test を書く必要がある
- **report.md に値が 2 つ出る**: レポート読者が「どちらを見ればよいか」迷う可能性があるため、`report.md` 冒頭にモードの位置付けを必ず書く

### Superseded への備え

- 将来、新しいモード（例: log-likelihood based）を追加する場合は ADR-0002 を Superseded とし、新 ADR を起こす
- 既存の mode 名 `paper` / `research_extended` は v1.0 まで変更しない

## References

- レビュー指摘の逆参照:
  - `docs/reviews/review-privacy.md` 指摘 1（原論文式との整合）
  - `docs/reviews/review-python.md` 指摘 4（セル数正規化）
  - `docs/reviews/review-python.md` 指摘 14（禁止ペナルティをハード制約に移す → 本 ADR とは別だが関連）
- `docs/reviews/action-plan.md` §1.1、§2A 「§11.4」
- `docs/spec/spec.md` §11.4、§15.1
- 原論文: Murata, Harada, Masui (2017) 式(1), (3), §4
- 関連 ADR: ADR-0001（内部表現、本モードの差分更新は ADR-0001 に従う）
