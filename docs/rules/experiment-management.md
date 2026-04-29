# 実験管理ルール

合成人口の生成・評価・改善は、実験に依存する研究開発です。
ここでは **実験の再現性・記録性・解釈の説明責任** を担保するためのルールを定めます。
「誰が後から見ても同じ結果が出せる」「なぜその結果をそう解釈したかが分かる」ことを最低基準にします。

---

## 1. 基本原則

1. **実験と本体コードを分ける**: 本体は `src/` / `synthpop_jp/`、実験は `experiments/` 配下
2. **必ず記録する**: 実験条件・seed・データ・結果・解釈をセットで保存する
3. **失敗も残す**: 仮説通りにならなかった実験も捨てない（後で見返す価値がある）
4. **Issue と相互参照する**: Issue → 実験レポート / 実験レポート → Issue のリンクを両方向で張る
5. **HTML 化する**: 最終成果物の実験レポートは HTML に変換して保存する（詳細: [`html-reporting.md`](html-reporting.md)）

---

## 2. ディレクトリ構成

```
experiments/
  2026-04-23-sa-convergence-baseline/      # <日付>-<slug>
    README.md                              # 短い概要（なくても可）
    report.md                              # 実験レポート（雛形: docs/templates/experiment_report.md）
    report.html                            # Markdown を HTML 化したもの
    config.yaml                            # 実験設定（seed を含む）
    run.py                                 # 実験スクリプト（もしくは notebook + 変換結果）
    data/                                  # 入力データへの参照（実体は別管理）
      INPUT.md                             # 使用データのバージョン・取得方法
    output/
      log/                                 # ログ
      metrics/                             # 指標 CSV / JSON
      figures/                             # 図版
      snapshots/                           # 生成結果の保存
```

- 1 実験 = 1 ディレクトリ。複数条件の比較は同一ディレクトリ内で扱う（結果 CSV を条件ラベル付きで並べる）
- ディレクトリ名の形式: `<YYYY-MM-DD>-<slug>`
  - slug は英小文字ハイフン区切り、目的を 2〜4 語で表す
  - 例: `2026-04-23-sa-convergence-baseline`, `2026-05-02-cap-vs-dcr`

---

## 3. 必ず記録する項目

実験レポート（`report.md`）には最低以下を含めます。テンプレ: [`docs/templates/experiment_report.md`](../templates/experiment_report.md)。

| 項目 | 例 |
|---|---|
| 実験名 | SA 収束性ベースライン |
| Issue / ブランチ / コミット SHA | `#42` / `feature/42-add-sa-core` / `1234abc` |
| 目的 | SA の温度スケジュールごとの目的関数減衰を比較する |
| 仮説 | 線形冷却より指数冷却のほうが 1000 iter 以内に目的関数を下げる |
| 条件 | N=10k, iter=1000, 温度スケジュール={linear, exp}, seed={1..5} |
| 使用データ | 国勢調査 2020 小地域クロス表 v1.0（`data/INPUT.md` 参照） |
| 評価指標 | 目的関数 L1、制約違反率、計算時間 |
| 結果 | （数値要約と主要図） |
| 解釈 | （非技術者にも通じる 1 段落） |
| 制約 | サンプルが小地域 1 件のみ。一般化には追試必要 |
| 次アクション | 条件を 5 小地域に拡大した追試を `experiments/2026-04-30-...` で実施 |
| **ピーク RSS** | 例: 358MB（100k 世帯、N×iter ごとに記録）。Issue #51 ルール |

---

## 4. 再現性の具体ルール

### seed

- 乱数は `numpy.random.default_rng(seed)` 経由のみ
- seed は `config.yaml` に書き、スクリプトは config から読む
- 複数 run の seed は `[1, 2, 3, 4, 5]` のようにリスト固定（ランダム生成しない）

### データ

- 入力データは `experiments/<...>/data/INPUT.md` に **バージョンと取得方法** を書く
  - 例: `census_2020_v1.0 / s3://.../census-2020-v1.0.parquet / sha256=...`
- 大きなデータは git に入れない。代わりに再取得手順を INPUT.md に書く

### コード状態

- 実験開始時の `git rev-parse HEAD` を `report.md` に記録
- 実験中にコードを変更した場合、**変更後に実験を再実行** してから結果を報告する
- 再実行が重い場合、変更前後の SHA を両方記録した上で「どちらの SHA の結果か」を明記

### 実行コマンド

- `report.md` の「再現手順」欄に、1 コマンドで走る形を書く
  - 例: `uv run python experiments/2026-04-23-sa-convergence-baseline/run.py --config config.yaml`

### 重さタグ（WEIGHT.md）

実験ディレクトリ直下に `WEIGHT.md` を必ず 1 ファイル置きます。中身は `light` または `heavy` のどちらか 1 語のみ。

```
heavy
```

- **light**: SA 単独で peak RSS が概ね 200MB 以下に収まる軽い実験。N ≤ 10k 世帯が目安。
- **heavy**: 並列稼働すると物理 RAM を圧迫しうる実験。**N ≥ 100k 世帯**を含む SA は heavy（Issue #51 実測 358MB が根拠）。

`scripts/pm_status.py`（`make pm`）が `experiments/*/WEIGHT.md` を読み、worktree ごとに **「最も重いタグ」**を表示します。
**heavy worktree が 1 本でも active な間は、新規 Agent の起動を控える**運用ルールです（詳細: [`.claude/skills/multi_agent_orchestration.md`](../../.claude/skills/multi_agent_orchestration.md) §「重実験 worktree が active な間は新規 Agent を起動しない」）。

`light` / `heavy` 以外の値は無効として扱われ、warning ログを出して None として処理されます。

### ピーク RSS の記録

`report.md` の「結果」または「条件」欄に、計測したピーク RSS を必ず記載してください。

- 計測手法は `experiments/2026-04-29-sa-memory-profile/peak_rss.py`（subprocess + `ps -o rss=` サンプリング）が参考実装
- 計測値は規模（N、iter）と一緒に表で残す
- 100k 世帯以上を含む実験では、計測値が `WEIGHT.md=heavy` の根拠になる

---

## 5. 実験と本体コードの分離ルール

- `experiments/` 配下から `src/` / `synthpop_jp/` を import するのは **OK**
- `src/` / `synthpop_jp/` から `experiments/` を import するのは **禁止**
- 実験スクリプト内のユーティリティで汎用化すべきものは、**本体に引き上げてテストを書いてから** 再度実験に使う

こうすることで、実験コードが本体の依存グラフを汚さず、本体は TDD を守れます。

---

## 6. 失敗実験の扱い

- 失敗（= 仮説を支持しない結果）でも、実験ディレクトリは消さない
- `report.md` の「解釈」で **なぜ失敗したと考えられるか** を書く
- 失敗から派生した追試があれば、`next-action` 欄で次の実験ディレクトリ名にリンクする
- 失敗を共有する Issue コメントには、`report.html` へのリンクを必ず添える

失敗実験は後の仮説構築の材料になります。「恥ずかしいから消す」をしないこと。

---

## 7. 実験結果とコード変更を混ぜないルール

- 1 PR で「実験結果の追加」と「本体コードの機能追加」を同時にやらない
- 実験で振る舞いが変わるコードを書いた場合、順序は以下のいずれか:
  1. **先にコード変更 PR** → merge 後、**実験 PR** を別立てで出す
  2. 同 PR 内だが、**実験結果は別コミット** にし、PR 本文で「検証実験」として明記する
- 理由: コード変更と実験結果の対応関係が履歴から追えなくなり、後で「どのバージョンでこの結果が出たか」が分からなくなるため

---

## 8. Issue と実験レポートの相互リンク

- 実験を伴う Issue では、**Issue 本文 or コメント** に `experiments/<日付>-<slug>/report.html` へのリンクを書く
- 実験レポートの冒頭に、対応 Issue 番号を書く（`Issue: #42`）
- PR 本文にも「実験 / 検証」欄に HTML レポートへのリンクを書く

この三点（Issue / レポート / PR）を必ず相互に辿れる状態にします。

---

## 9. 良い実験記録の例（抜粋）

```markdown
# SA 収束性ベースライン

- Issue: #42
- Branch: feature/42-add-sa-core
- Commit: 1234abc
- 実施日: 2026-04-23

## 目的
SA の温度スケジュールごとに、目的関数の減衰曲線を比較する。

## 仮説
指数冷却は 1000 iter で L1 を初期値の 1/4 以下まで落とす。線形冷却は 1/2 止まりと予想。

## 条件
- N = 10,000
- iter = 1,000
- 温度スケジュール: {linear, exp(α=0.95)}
- seed: {1, 2, 3, 4, 5}

## 結果
|scheme | median L1 at iter=1000 | success rate |
|---|---|---|
|linear | 0.48 | 4/5 |
|exp    | 0.21 | 5/5 |

（figures/loss_curve.png）

## 解釈
指数冷却は仮説通り 1/4 以下に到達。線形冷却は仮説通り 1/2 付近で停滞した。
ただし N=10k 1 小地域のみでの結果であり、一般化には追試が必要。

## 制約
- データは 1 小地域のみ
- iter=1000 は最終仕様ではなく、暫定値

## 次アクション
- 5 小地域に拡大した追試 → `experiments/2026-04-30-sa-convergence-5areas/`
- 最終 iter 数の決定実験 → `experiments/2026-05-02-sa-iter-tuning/`

## 再現手順
uv run python experiments/2026-04-23-sa-convergence-baseline/run.py \
    --config experiments/2026-04-23-sa-convergence-baseline/config.yaml
```

---

## 10. チェックリスト

### 実験開始前
- [ ] 仮説と成功 / 失敗の判定基準を先に決めた
- [ ] config.yaml に seed・条件を書いた
- [ ] 入力データのバージョンを INPUT.md に書いた

### 実験完了後
- [ ] 結果（数値・図）が保存されている
- [ ] 解釈が非技術者にも通じる 1 段落で書かれている
- [ ] 制約を明記した
- [ ] 次アクションを書いた
- [ ] report.html が生成されている
- [ ] Issue と相互リンクされている
