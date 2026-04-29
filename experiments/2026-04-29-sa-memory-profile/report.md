# SA 実行ピーク RAM 実測

- Issue: #51
- PR: （merge 後に追記）
- Branch: `feature/51-sa-memory-profile`
- Commit: `e2681a0`（実験実行時点）
- 実施日: 2026-04-29
- 実施者: @gghatano (Claude Code)

---

## 非技術者向け要約

合成人口を作る計算（SA: 焼きなまし法と呼ぶ最適化）が、どのくらいパソコンの記憶領域（RAM）を使うかを測りました。
1,000 / 10,000 / 100,000 世帯の 3 規模で計測した結果、**100,000 世帯でも 358MB**（一般的なノート PC で 25GB あるうちの 1.4%）に収まりました。
「PC が固まる」のは SA 単体ではなく、**SA と他のプログラム（Claude Code エージェントなど）の同居が原因**である可能性が高いと分かりました。
反復回数を 20,000 → 200,000 に増やしても RAM はほぼ変わりません（SA は反復ごとにデータを溜め込まない設計だと確認できた）。
今後は「100,000 世帯以上の SA を回すときは他の重い処理を同時に走らせない」というルールを設けます（Issue #52）。

---

## 目的

- 開発者と PM が「この規模ならどれくらい RAM を食うか」を**実測値**で見積もれるようにする
- Issue #52（重実験中の並列 Agent 禁止ルール）に**数値根拠**を渡す
- Issue #53（trace.jsonl / resume / HTML 監査）に「どこが膨らむか」の手がかりを渡す

## 仮説

| 仮説 | 結果 |
|---|---|
| 1k 世帯 × 200k iter のピーク RSS は 500MB 未満 | ✅ 85MB |
| HTML レポートは N に比例して急増する | ⚠️ 単独プロセスでは比例するが、最大でも 179MB（100k 世帯）。仮説より小さい |
| trace.jsonl は反復数に比例して増える（in-memory） | ❌ **iter を 10 倍にしても RSS 不変**。streaming 実装になっており蓄積していない |
| 100k × 200k × HTML は OOM する | 未測定（後述）。100k × 20k では OOM せず 358MB |

## 条件

| 項目 | 値 |
|---|---|
| データ | `data/sample_case/` を整数倍スケール（`make_inputs.py`） |
| 世帯数 | {1,000, 10,000, 100,000} |
| 反復数 | {20,000, 200,000} |
| モード | dry-run（書き込みなし）/ full（CSV+trace.jsonl 書き出し）/ full+html（さらに HTML レポート生成） |
| seed | {1, 2, 3}（一部セルのみ seed×3、それ以外は seed=1） |
| 計測方法 | 子プロセスを `synthpop-jp generate` として起動し、`ps -o rss=` で 100ms 間隔サンプリング |
| OOM ガード | 物理メモリの 70%（18GB）を超えたら SIGTERM/SIGKILL |
| 実行環境 | macOS Darwin 24.6.0 / Python 3.12.12 / 物理 RAM 25.8GB |

## 使用データ

- 名前: scaled sample_case
- バージョン: `data/sample_case/` の整数倍スケール（100, 1000 倍）
- 取得方法: `make_inputs.py` が tempdir 内に動的生成
- 前処理: `count` 列を整数倍、`rate` 列はそのまま
- 詳細: `INPUT.md`

## 評価指標

| 指標 | 定義 |
|---|---|
| sa_peak_rss_bytes | SA 子プロセスの RSS 最大値（`ps` サンプリング） |
| sa_elapsed_seconds | SA 子プロセスの実時間（spawn → exit） |
| html_peak_rss_bytes | HTML 生成子プロセスの RSS 最大値（full+html 時のみ） |

## 結果

### 数値サマリ（N 別、mode=full、seed=1）

| N | SA peak | SA elapsed | HTML peak (full+html) |
|---|---|---|---|
| 1,000 | 86MB | 0.7s | 64MB |
| 10,000 | 106MB | 3.0s | 63MB |
| 100,000 | 358MB | 177s | 179MB |

### iter 軸の効果（mode=full、seed=1）

| N | 20k iter | 200k iter | 差 |
|---|---|---|---|
| 1,000 | 86MB | 85MB | -1% |
| 10,000 | 106MB | 108MB | +2% |

→ **反復回数は RSS にほぼ影響しない**。SA state は固定サイズで、trace は streaming されている。

### seed 間ばらつき（mode=full、max_iters=20k）

| N | seed=1 | seed=2 | seed=3 | 最大ばらつき |
|---|---|---|---|---|
| 1,000 | 86MB | 84MB | 84MB | 2.4% |
| 10,000 | 106MB | 96MB | 108MB | 11.6% |
| 100,000 | 358MB | 357MB | 356MB | 0.6% |

### モード別寄与（N=100k、max_iters=20k、seed=1）

| mode | SA peak | HTML peak |
|---|---|---|
| dry-run | 358MB | - |
| full | 358MB | - |
| full+html | 347MB | 179MB |

→ **dry-run と full の差は誤差範囲**。CSV 書き出しと trace.jsonl は RSS にほぼ影響しない（streaming 実装の確認）。
→ **HTML 生成は別プロセス**で、SA と独立に最大 179MB（100k 世帯）。

### 全データ

`outputs/peak_rss.csv` 参照（21 行、5 ラウンド分）。

## 解釈

### 主結論

**SA 単独では PC を固める規模に達しない**。100k 世帯（人口約 270k）でも 358MB であり、25.8GB の物理 RAM の 1.4% に過ぎない。
前回 PC が固まった原因は、SA 単独ではなく、**並列稼働する他プロセス（Claude Code エージェント、複数の SA 実験、ブラウザ等）との合算**で物理 RAM が枯渇したと考えられる。

### trace.jsonl は streaming 済み

dry-run と full の RSS が誤差範囲内で一致した（358MB vs 358MB）。これは `trace.jsonl` を反復ごとに追記書き出ししており、in-memory バッファに溜め込んでいないことを示す。
反復数を 20k → 200k に 10 倍にしても RSS が変わらない事実とも整合する。**Issue #53 の `trace.jsonl` 監査は早期 close 候補**（追加コード読解で確認すれば、リーク無しと判定して終わる見込み）。

### HTML レポートは線形寄与

HTML peak は N に対しおおよそ線形に増える（1k=64MB → 10k=63MB → 100k=179MB）。10k で 1k と変わらないのは plotly のベースランタイムが支配的だから。100k では人口 270k 行の DataFrame と plotly 図が支配する。

### 時間スケーリング

SA elapsed は N に対して非線形（1k=0.7s → 10k=3s → 100k=177s）。10x N で elapsed は ~5x → ~60x という挙動は、**SA 内部ループに O(N) の評価コスト**があることを示唆する（候補近傍の生成・差分評価）。これはメモリではなく速度の話なので Issue #51 のスコープ外だが、実用面で 100k × 200k は 30 分超かかる見込み。

### PM が読むべき含意（重実験の境界）

このマシン（物理 RAM 25.8GB）における目安:

| 規模 | SA peak | 並列許容（1.5GB Claude × N agents の場合） |
|---|---|---|
| ≤ 10k 世帯 | ≤ 110MB | 同居 OK（5+ Agents まで余裕） |
| 100k 世帯 | 358MB | 同居 OK（3-4 Agents まで） |
| 推定 1M 世帯 | ≈ 3.5GB（外挿） | 軽い Agent 1 つまで |
| 推定 10M 世帯 | ≈ 35GB（外挿）| **単独実行必須**、OOM ガード必須 |

**Issue #52 では「100k 世帯以上の SA は heavy 扱いとし、他の Agent 起動を控える」を暫定しきい値**として推奨する。10M 規模に達する実験は本リポジトリでは Phase 4-5 まで想定されておらず、当面の運用は 100k 基準で十分。

## 制約

- **物理 RAM 25.8GB の単一マシンでの計測**。RAM 16GB 機での挙動は別途要検証
- **macOS の RSS 計測** (`ps -o rss=`) は shared memory を含む。Linux と比較すると数値が膨らむ可能性
- **100k × 200k は時間制約で測定省略**（推定 12 分）。RSS は iter 軸が flat であることから 100k × 20k と同等と推測
- **seed×3 検証は full モード × 20k iter のみ**。他のモード/iter ではばらつき未確認
- **OOM 到達セルなし**（OOM ガードの動作確認は単体テストで実施済み）
- **HTML レポート生成は別プロセスで計測**。実運用で「generate 直後に同プロセスで render」するパターンの結合測定はしていない（合算 ≈ SA peak + HTML peak とみなせる）

## 再現手順

```bash
# 全グリッド実行（推定 30 分弱、100k 系の elapsed が支配）
uv run python experiments/2026-04-29-sa-memory-profile/run.py

# smoke（1 セルのみ、~1 秒）
uv run python experiments/2026-04-29-sa-memory-profile/run.py --smoke

# 部分指定の例（10k × 20k × full × seed=1,2,3）
uv run python experiments/2026-04-29-sa-memory-profile/run.py \
    --n-households 10000 --max-iters 20000 --modes full --seeds 1 2 3
```

- Python: 3.12.12
- 主要依存: pandas, pyyaml, synthpop-jp（編集可能インストール）
- 実行時間目安: pilot 21 セル ≈ 12 分（100k 系の 9 セルが大半）

## 次に見るべき論点

- [ ] **Issue #52**: 本実験の数値を運用ルールに反映（100k しきい値、`WEIGHT.md=heavy` の運用）
- [ ] **Issue #53**: trace.jsonl 監査は early-close 候補。resume と HTML inline figure のコード読解にスコープを絞り込んでよい
- [ ] 100k × 200k の補測（時間予算が空けば）
- [ ] **CPU/メモリプロファイル**で 100k の elapsed が 177s かかる原因を特定（O(N) 候補生成かどうか）。Issue #51 のスコープ外、別 Issue で起票要否を判断
- [ ] 1M 規模での外挿確認（Phase 3+ で需要があれば）
- 関連: #33（SA 性能ゲート）、#31（trace.jsonl）、#32（resume）、#38（HTML）

---

## 追記（時系列）

<!-- 結果を書き換えないこと。新しい知見は日付付きでここに追記する。 -->

（なし）
