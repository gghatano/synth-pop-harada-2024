---
name: 2_issue_impl
description: 段階 1 で固めた計画に基づいて TDD で実装を進める。小さいコミットを積み、実験と本体コードを分離し、Issue に逐次記録する。
---

# SKILL: 2_issue_impl — TDD で小さく実装する

## 目的

段階 1 の計画を、**小さく検証可能な単位** に分けて実装する。実装の各ステップが「落ちるテスト」と「それを通す最小コード」で進むため、どこで何が壊れたかが常に追える状態を保つ。

## 使う場面

- `1_issue_plan` が完了し、worktree と計画が揃った後
- 実装の途中で新しい観点が出て、小さな実装サイクルを再開したいとき

## 入力

- 対象 Issue 番号と計画（Issue コメント または `docs/plans/issue-<番号>.md`）
- 作成済みの worktree / feature ブランチ

## 実施手順

1. **作業場所を確認する**
   ```bash
   pwd                          # gitworktree/feature-<issue番号>-<keyword> 配下であること
   git rev-parse --abbrev-ref HEAD   # feature/<issue番号>-... であること
   ```
2. **テストを 1 つ書く（Red）**
   - 計画のテスト観点から、**最小の 1 項目** を選ぶ
   - 落ちることを確認してからコミットする（テストが落ちない = 新しい振る舞いを表現できていない）
   - コミットメッセージ例: `test: <what the test asserts> (refs #42)`
3. **最小実装でテストを通す（Green）**
   - 必要最小のコードだけ書く。「ついでに他の改善」は禁止
   - コミット例: `feat: <behavior> to pass <test name> (refs #42)`
4. **整理する（Refactor）**
   - テストが通っている状態で、命名・重複・責務分割を整える
   - コミット例: `refactor: extract <module> (refs #42)`
5. **2〜4 を小さく繰り返す**
   - 1 サイクル = 数十行〜200 行程度が目安
   - 1 日分の作業を 1 コミットにまとめない
6. **実験が必要なら `experiments/` 配下で走らせる**
   - 本体コードは `src/` / `synthpop_jp/`、実験スクリプトは `experiments/<日付>-<slug>/` に置く
   - 設定は `config.yaml` のような宣言的形式で、seed・データパス・出力先を明示
   - 結果は `experiments/<日付>-<slug>/output/` に出し、レポートを `report.md` にまとめる
   - 詳細: [`docs/rules/experiment-management.md`](../../docs/rules/experiment-management.md)
7. **節目ごとに Issue へ進捗コメントを残す**
   「何をやったか」「想定通りだったか」「次に何をやるか」を 3 行でよい。実装の判断の軌跡が残ると、レビュー時の理解が早い
8. **ログ・seed・出力先を固定する**
   - ログは `logging` モジュールで出力し、print は使わない
   - 乱数は `numpy.random.default_rng(seed)` 経由で、seed を config に書いて読む
   - 出力先はコマンドライン引数で上書き可能にし、デフォルトは `experiments/.../output/`

## 出力物

- テスト付きの実装コミット列
- 実験を行った場合は `experiments/<日付>-<slug>/` 一式
- Issue コメントに実装メモ・実験メモを追記

## 完了条件

- [ ] 計画で挙げたテスト観点のうち、必須項目がすべてテストとして存在する
- [ ] すべてのテストが通る（`pytest` / `uv run pytest` が green）
- [ ] 実験を行った場合、seed と設定が再現可能な形で保存されている
- [ ] 実験結果は Markdown レポート化されている（HTML 化は段階 3 以降でも可）
- [ ] コミットが意味単位で小さく分かれている

## 注意点

- **探索的コードと本体コードを混ぜない**。`experiments/` の Jupyter Notebook や one-shot script は `src/` に import させない
- **「とりあえず動く」で止めない**。通ったら必ず Refactor の一呼吸を入れる
- **コミットログを荒らさない**。`wip`, `fix fix`, `debug` のようなメッセージは後から読めない
- **TDD を厳守できない場面を認める**。例えば「まず出力を目で見たい」系の可視化は、最初に手で走らせてから後追いでテストを書く。ただしその判断は Issue に記録する
- コミット前にフック (`pytest`, lint) が走るように設定がある場合、**スキップしない**。落ちる理由をつぶす

## コミット単位の考え方

| 粒度 | 良い例 | 悪い例 |
|---|---|---|
| テスト追加 | `test: SA delta apply preserves origin array` | `tests` |
| 最小実装 | `feat: add delta.apply for SA iteration` | `WIP SA` |
| 整理 | `refactor: move Pop dtype into types module` | `misc cleanup` |
| 設定変更 | `chore: pin numpy>=2.0 in pyproject` | `update deps` |

## GitHub Issue に追記すべきこと（実装中）

- 実装開始時: 取り組み始めたことと、最初に触るファイル
- 途中: 予想と違った観察、方針転換、追加の気付き
- 実験実行時: 実験 ID（`experiments/<日付>-<slug>`）と、走らせた条件、速報の結果
- 実装完了時: テスト数、カバレッジ概況、次段階（レビュー）に渡す論点
