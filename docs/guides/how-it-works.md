# 仕組みと使い方ガイド — synthpop-jp が何をどう動かしているか

このドキュメントは、`synthpop-jp` を使う人が「いま自分の手元で何が起きているのか」を理解しながら使えるように、**手法と CLI の使い方を順序立てて 1 ファイルにまとめた読み物** です。

専門用語が初めて登場する箇所では、一言の補足を必ず添えています。深く知りたい場合は各セクションのリンク先（spec / 個別レポート）に進んでください。

最初に読むべき関連ドキュメント:
- 現在地と Phase ごとの実績は [`docs/reports/2026-04-30-progress-overview.md`](../reports/2026-04-30-progress-overview.md)
- インストールと最短実行は [`README.md`](../../README.md) §3〜§4

---

## 1. 何のための道具か

公開されている統計（家族類型別世帯数、年齢分布、世帯サイズ分布など、すでに集計済みの表）だけを材料に、**統計と整合する世帯と個人の人工的な個票** を作るための道具です。

実在する個人の情報を使わずに集計表だけから個票を作るので、プライバシーを守りつつ、「もし個票があったら何ができるか」をシミュレーションできます。例えば、政策効果の推計や、データ分析パイプラインのテスト用データとして使えます。

ただし、出来上がるのは **統計的な意味で** 整合した架空の人口です。実在する個人の代理ではありません。

---

## 2. 全体像 — 4 つの軸

このプロトタイプは、4 つの軸を独立に組み合わせて動かす設計になっています。

| 軸 | 役割 | 具体例 |
|---|---|---|
| **作る** | 統計を満たす初期人口を作る／少しずつ動かす | 初期生成、遷移（transition） |
| **整える** | 「どれだけ統計に合っているか」を数値化する | 目的関数（objective） |
| **評価する** | 出来上がった人口の品質・リスクを測る | 評価器（evaluator） |
| **比較する** | 異なる設定の SA を回して優劣を判定する | compare runner |

「整える」までは合成データを作る最適化ループの内側です。「評価する」「比較する」は完成した合成データに対する後付けの分析で、最適化ループの外側です。

この分離により、新しい遷移や評価指標を足したいときも、他の軸に手を入れずに 1 ファイル単位で拡張できます。

---

## 3. 作る軸 — 初期生成と遷移

### 3.1 初期人口を「ゼロから」作る

最初の合成人口は、9 種類の家族類型（夫婦のみ、夫婦と子ども、単身世帯、母子世帯、…）について、世帯数の集計表に従って世帯を並べることから始まります。続いて、それぞれの世帯に属する個人の年齢を、役割（戸主・配偶者・子・親）と性別の条件付き分布からサンプリングします。

このとき、`use_zero_error_init=true` を指定すると、Largest Remainder 法（決定論的な丸め方の 1 つ。各カテゴリの「割当数の小数部」が大きい順に切り上げる）で「世帯数の合計が統計と完全一致する」状態にできます。SA が始まる時点で初期誤差を 0 にできるので、最適化の伸びしろが目的関数の改善だけに集中します。

詳細: spec §3、`src/synthpop_jp/initial/`

### 3.2 SA で少しずつ動かす — 焼きなまし法とは

初期人口は統計の一部しか合っていないため、それを目的関数（次節）に従って少しずつ修正します。この修正に使うアルゴリズムが SA（Simulated Annealing、焼きなまし法）です。

SA のふるまいは次のとおりです。

1. 現在の人口にちょっとした変更（**遷移**）を加える候補を提示する
2. その変更で目的関数が下がる（良くなる）なら、必ず受け入れる
3. 上がる（悪くなる）場合でも、ある確率で受け入れる
4. 反復を進めるにつれて、悪化を受け入れる確率を下げていく

「悪化も時々受け入れる」のは、近視眼的な改善（局所最適）に閉じ込められないためです。冷却スケジュール（温度を下げる速さ）を `T0` と `alpha` で制御します（`T_next = T_current × alpha`）。

### 3.3 3 種類の遷移

具体的な変更操作は次の 3 種類です。

| 遷移 | 内容 | spec |
|---|---|---|
| `AgeChangeTransition` | 1 人の年齢を、同じ家族類型・役割・性別の条件付き分布からサンプリングし直す | §12.2A |
| `AgeSwapTransition` | 同じ家族類型・性別の 2 人の年齢を交換する。**家族類型別の年齢ピラミッドを保ったまま** 個人の組み合わせだけを変えられる | §12.2B |
| `HybridTransition` | age-change と age-swap を確率 `p_change` で混ぜる。`linear` スケジュールを使うと、序盤は age-change 中心、終盤は age-swap 中心に切り替わる | §12.2C |

ハード制約（「親は子より 14 歳以上年上」「夫婦の片方が未成年でない」など spec §11.5 の制約）は、遷移の段階で `propose` がリトライして弾きます。目的関数には入れず、**遷移の中で物理的に守る** 設計です。

詳細: `src/synthpop_jp/optimize/transitions.py`

---

## 4. 整える軸 — 目的関数

目的関数 f(A) は「現在の合成集団 A が目標の統計群からどれだけずれているか」を数値化したものです。SA はこの値を下げる方向に人口を動かします。

### 4.1 3 つのモード

`configs/base.yaml` の `objective_mode` で 3 種類を選択できます。

| モード | 統計数 | 内容 |
|---|---|---|
| `minimal` | 5 | 家族類型別世帯数、年齢分布、世帯サイズ分布、性別比、役割比 |
| `extended` | 5 + 10 + 2N | minimal に family_type × sex の人口ピラミッド 10 統計を追加（PR #72） |
| `strict_extended` | 3 + 2N | Murata 式 (3) に厳密に準拠（D, E 統計を除外、PR #85） |

`extended` で増えるのは「家族類型ごとに男女別の年齢ピラミッドが、目標の家族類型別ピラミッドにどれだけ一致するか」です。家族構造に依存した年齢パターンをきちんと再現したいときに有効です。

### 4.2 差分更新が性能の鍵

人口は数百万人規模になりますが、1 step で動くのは 1〜2 人です。そのため、目的関数を毎回ゼロから計算し直すのではなく、変更された分だけ差分で更新する仕組み（`ObjectiveState._compute_delta_for_change`）を入れています。

これにより 1 step あたりの計算時間が 1.5 μs 程度に収まり、20 万反復でも 5 秒程度で終わります（[Phase 2 ベンチマーク](../reports/phase-02-benchmarks.md)）。

ただし、差分更新の実装にバグがあると SA が誤った勾配で動き続けるため、`test_apply_change_keeps_score_consistent`（差分更新と全再計算の一致テスト）を必ず残しています。

詳細: `src/synthpop_jp/optimize/objective.py`、spec §11.3

---

## 5. 評価する軸 — 3 つの評価器

SA で出来上がった合成人口を、3 種類の評価器で測ります。すべて `synthpop-jp evaluate` で同時実行され、結果は `metrics.json` に書き出されます。

### 5.1 統計誤差（aggregate L1）

目的関数と同じ統計群について、**目標値からの絶対誤差の合計**（L1 距離）を統計種別ごとに分けて出力します。`aggregate.l1.total` / `aggregate.l1.family_type` / `aggregate.l1.age` のように細分化されているため、「どの統計が合わせきれていないか」が一目で分かります。

目的関数の値そのものよりも、人間が読んで意味を取りやすい数値です。

### 5.2 rare cell（低頻度カテゴリ監視）

目的関数を強く最適化すると、低頻度のカテゴリ（例: 80 歳以上の特定の家族構成）に過適合し、「合成データには出現するが現実にはありえない組み合わせ」が混じることがあります。

`RareCellEvaluator` は family_type × age の cell ごとに「人数が k 人以下の cell の割合」を計算します。`rare_cell.unique_rate`（k=1）が高いと過適合の兆候です。

### 5.3 CAP / TCAP（属性推論リスク）

合成データから個人の属性をどれだけ推論できるかを測る指標です（Harada 2024 §5.2、spec/metrics.md §5.2）。

- **CAP**（Generalized CAP）: 合成集団内で同じ属性パターンを持つレコード群の中に、ある target カテゴリがどれだけ集中しているか
- **TCAP**: それを実集団の真の分布に対して校正した値

合成データだけからは「個人の特定」までは行けない作りでも、**特定の属性パターンを持つ人の他の属性が高確率で当たる** ようなら問題です。CAP/TCAP はこの「集中度」を 0〜1 の値で出します。

CAP は実個票（`real-persons-csv`）を渡したときだけ計算されます。**目的関数には入れず観測のみ** という設計判断は spec §11.6 の「目的関数を強く最小化すると低頻度カテゴリが過適合し、属性推論耐性が下がる」という警告に対応しています。

### 5.4 評価器の追加方法

`synthpop_jp.evaluators` の entry_point に新しい Evaluator を登録すると、`evaluate` コマンドが自動的に拾います。Evaluator は次の Protocol を満たすだけで OK です。

```python
class Evaluator(Protocol):
    name: str
    def evaluate(self, pop: PopulationArrays) -> dict[str, float]: ...
```

詳細: `src/synthpop_jp/evaluate/`、spec §13

---

## 6. 比較する軸 — compare runner

「config A と config B、どっちが本当に良いのか？」を統計的に判定する仕組みです。

### 6.1 何をしているか

`synthpop-jp compare -c configs/A.yaml -c configs/B.yaml --n-seeds 10` を実行すると、

1. 各 config を 10 個の独立した seed で SA 実行する
2. 指定した metric（デフォルトは `aggregate.l1.total`）の分布を 2 つ得る
3. 両者の差を Welch's t-test と Wilcoxon signed-rank で検定する
4. 複数 metric を比較する場合は Holm 補正で多重検定の影響を抑える
5. percentile bootstrap で 95% 信頼区間を出す

結果は `outputs/compare/compare.json`（機械可読）と `compare.md`（人間可読）に書き出されます。

### 6.2 なぜ必要か

SA は乱数に依存するため、同じ config でも seed が違えば結果が変わります。「config A の方が L1 が小さかった」が **たまたまの seed の差** なのか **本当の手法の差** なのかを切り分けるには、複数 seed で回して統計検定するしかありません。

10〜30 seed あれば、Phase 3 規模の比較なら有意差は検出できる範囲に入ります（spec §15.2 の比較計画）。

詳細: `src/synthpop_jp/compare/`、PR #87 / #88

---

## 7. CLI の使い方 — 一連の流れ

ここまでの 4 軸が、コマンドラインからは次の順序で使えます。

### Step 1: インストール確認

```bash
git clone https://github.com/gghatano/synth-pop-harada-2024.git
cd synth-pop-harada-2024
uv sync --frozen
uv run synthpop-jp --help
```

### Step 2: 設定の妥当性チェック

```bash
uv run synthpop-jp validate-config configs/base.yaml
# ✓ Config is valid: configs/base.yaml
```

YAML が壊れていたり値が範囲外だと、行番号付きでエラーが出ます。

### Step 3: 動作確認 — quickstart

同梱のダミーデータを使って、初期生成だけを実行します（SA は走りません）。

```bash
uv run synthpop-jp quickstart --seed 42
# outputs/quickstart/synthetic_households.csv
# outputs/quickstart/synthetic_persons.csv
# outputs/quickstart/metrics.json
```

10 秒以内（実測 1.1 秒）に 3 つのファイルが出来上がります。中身は CSV なので、Excel や pandas でそのまま開けます。

### Step 4: SA 最適化 — generate

`generate` は初期生成のあとに SA を回します。`configs/base.yaml` の `annealing` セクションで温度・反復数・冷却率を制御します。

```bash
uv run synthpop-jp generate --config configs/base.yaml --seed 42
```

SA の進行は `metrics.json` の `best_score` などから追えます。長時間の実行を中断したいときは Ctrl+C で止め、`--resume <checkpoint>` で続きから再開できます。

### Step 5: 評価 — evaluate

`generate` が出力した `synthetic_persons.csv` を読み込み、3 種の評価器を順次実行します。

```bash
uv run synthpop-jp evaluate --config configs/base.yaml
# metrics.json に aggregate.l1.* / rare_cell.* キーが追記される
# report.md に Harada 2024 Table 13 形式の表が追記される
```

CAP/TCAP も計算したい場合は、実個票（あれば）を渡します。

```bash
uv run synthpop-jp evaluate --config configs/base.yaml --real-persons-csv data/real/persons.csv
# metrics.json に cap.* キーも追記される
```

### Step 6: 比較実験 — compare

複数の config を統計検定付きで比較します。

```bash
uv run synthpop-jp compare \
  -c configs/minimal.yaml \
  -c configs/extended.yaml \
  --n-seeds 10 \
  --metrics aggregate.l1.total,rare_cell.unique_rate \
  --output-dir outputs/compare-2026-04-30
```

数分〜数十分かかります（n_seeds × max_iters に比例）。終了すると `compare.md` に「config A vs config B、p-value=0.012、95%CI=[-0.04, -0.01]」のような表が並びます。

---

## 8. 設定ファイルの読み方

`configs/base.yaml` は次のような構造です。

```yaml
seed: 42                          # 乱数シード（同じ seed なら bitwise 一致で再現）
input_dir: data/sample_case       # 入力 CSV のディレクトリ
output_dir: outputs/quickstart    # 出力先

annealing:
  T0: 100.0                       # 初期温度（高いほど序盤に広く探索）
  alpha: 0.999                    # 冷却率（1.0 に近いほどゆっくり冷える）
  max_iters: 1000000              # 最大反復回数
  evals_per_agent: 1000           # 1 人あたりの評価回数上限
  target_threshold: 0.0           # この値以下になったら停止（0 で無効）
  patience: 0                     # best_score 不改善反復の上限（0 で無効）
```

設定を変えるときの典型的なシナリオ:

| やりたいこと | 変えるところ |
|---|---|
| もう少し精度を上げたい | `max_iters` を 10 倍、`alpha` を 0.9999 に |
| 早く終わらせたい | `max_iters` を 1/10、`patience` を 1000 などに |
| 違う統計目標で動かす | `input_dir` を別ディレクトリへ |
| 別の遷移方式を試す | `transitions:` セクション（spec §12.2C を参照）を編集 |

詳細なフィールド定義は `src/synthpop_jp/config.py` の `Settings` モデルを参照してください。pydantic v2 のモデルなので、フィールド名・型・デフォルト値・バリデーション規則がコードからそのまま読めます。

---

## 9. もっと深く知りたいときに

### 仕組みについて

| 知りたいこと | 参照先 |
|---|---|
| Murata 2017 の元の式 | [`docs/spec/spec.md`](../spec/spec.md) §11〜§12 |
| Harada 2024 の評価軸 | [`docs/spec/metrics.md`](../spec/metrics.md) |
| 評価器の数式定義 | [`docs/spec/metrics.md`](../spec/metrics.md) §5〜§6 |

### 過去の実験から学ぶ

| 知りたいこと | 参照先 |
|---|---|
| 性能はどれくらい出るか | [`docs/reports/phase-02-benchmarks.md`](../reports/phase-02-benchmarks.md) |
| メモリ消費はどうか | [`experiments/2026-04-29-sa-memory-profile/report.md`](../../experiments/2026-04-29-sa-memory-profile/report.md) |
| Phase 3 拡張の方法論 | [`docs/reports/2026-04-29-phase3-extended-summary.md`](../reports/2026-04-29-phase3-extended-summary.md) |

### 自分で実装に手を入れたい

| 知りたいこと | 参照先 |
|---|---|
| 開発フロー全体 | [`docs/getting-started/development-workflow.md`](../getting-started/development-workflow.md) |
| Issue 駆動 | [`docs/rules/issue-driven-development.md`](../rules/issue-driven-development.md) |
| TDD ルール | [`docs/rules/tdd.md`](../rules/tdd.md) |
| 新しい評価器の追加 | [`CONTRIBUTING.md`](../../CONTRIBUTING.md) |

### コントリビュート

新しい遷移や評価器を追加したいときは、対応する Protocol を満たすクラスを書き、entry_points に登録するだけです。詳細は [`CONTRIBUTING.md`](../../CONTRIBUTING.md) を参照してください。

---

## 10. このドキュメントの位置付け

- **本ガイド (`how-it-works.md`)**: 「読みながら手元で動かして覚える」目的の読み物
- **進捗オーバービュー** ([`docs/reports/2026-04-30-progress-overview.md`](../reports/2026-04-30-progress-overview.md)): 「現在地・実績・残課題」の 1 枚要約
- **個別レポート** (`docs/reports/*.md`、`experiments/*/report.md`): その時点のスナップショット。書き換えず追記する

仕組みや CLI の挙動が変わったら、本ガイドも更新します。
