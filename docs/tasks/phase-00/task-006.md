# task-006: README の骨子配置（日本語 primary + 英語セクション併記）

## 目的

OSS の最初の入口を「30 秒で何が何か分かる」形で用意する。v0.1 (Phase 2 完了) までに英語版も含めて完成させるが、Phase 0 時点で骨子と主要セクションは出しておく。

## 前提・依存

- 命名・LICENSE 確定（task-003）
- CLI エントリ `synthpop-jp`（task-004 の pyproject.toml）
- Quickstart 実体は Phase 1 / Phase 2 で機能を実装してから中身を書く。本タスクは骨子とプレースホルダ。

## 成果物

### a. `/README.md`（日本語 primary）

冒頭:

```markdown
# synthpop-jp

Murata et al. (2017) の Simulated Annealing ベース合成人口生成手法の Python 再実装に、
Harada (2024) の有用性・秘匿性評価軸（ARD 等）と「生成→評価→改善」ループを載せた研究用ツールキット。

[English README](./README.en.md)
```

セクション:
1. 何ができるか（3 行）
2. 位置付け: Murata 2017 = 生成、Harada 2024 = 評価
3. インストール（`uv tool install synthpop-jp` または `uvx synthpop-jp ...`）
4. 30 秒 Quickstart（`uvx synthpop-jp quickstart` で sample_case を実行）
5. 入出力（spec §7 に委譲、要約のみ）
6. 類似 OSS との比較表:

| ツール | データ前提 | 手法 | 本実装との違い |
|---|---|---|---|
| synthpop (R) | サンプル個票必須 | CART / 条件付確率 | 集計表のみで動作 |
| SDV / CTGAN | 表形式データ全般 | GAN / copula | 世帯構造を保存する SA |
| PopulationSim / ActivitySim | 旅客需要向け | IPF | 目的関数カスタム可 SA |
| **synthpop-jp** | 公開集計表のみ | SA（Murata 2017） | 国勢調査テンプレ + ARD 評価内蔵 |

7. 引用（`CITATION.cff` / Murata 2017 / Harada 2024）
8. ロードマップ（v0.1 / v0.2 / v0.3 / v1.0 の要約）
9. コントリビューション（`CONTRIBUTING.md` へリンク）
10. ライセンス（Apache-2.0）

### b. `/README.en.md`（英語、骨子のみ）

v0.1 までに本体と同期。Phase 0 段階では section 見出しのプレースホルダで可。

### c. `/CONTRIBUTING.md`

- 開発セットアップ（`uv sync`, `pre-commit install`）
- ブランチ命名: ユーザー規約に従い `feature-<issue>-<keyword>`、worktree 配置は `gitworktree/` 以下
- PR フロー（CI 緑、ADR 要否、CHANGELOG 更新）
- 新 family_type 追加の 10 行例（Phase 1 で `register_family_type` API が出来たら更新）
- 新評価器追加の 20 行例（Phase 3.5 で `Evaluator` Protocol が出来たら更新）
- コミットメッセージ規約（任意: Conventional Commits 推奨程度）

## 受け入れ基準

- README.md が日本語で冒頭 3 行の位置付け説明を含む。
- 比較表が 4 行（synthpop R / SDV / PopulationSim / synthpop-jp）で埋まっている。
- `uvx synthpop-jp quickstart` のコマンド文字列が README と spec §17 で一致。
- CONTRIBUTING.md に worktree 配置規約（ユーザー CLAUDE.md 準拠）が記載されている。

## 推定規模

S〜M（半日）。

## 参照

- `docs/reviews/review-oss.md` 指摘 1, 4, 9, 11, 12 / 推奨追加ファイル節
- `docs/reviews/action-plan.md` §2C
