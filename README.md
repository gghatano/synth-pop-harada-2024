# synthpop-jp

Murata et al. (2017) の Simulated Annealing ベース合成人口生成手法の Python 再実装に、Harada (2024) の有用性・秘匿性評価軸（ARD 等）と「生成→評価→改善」ループを載せた研究用ツールキット。

[English README](./README.en.md)

---

## 1. 何ができるか（3 行）

- 公開されている **国勢調査の集計表のみ** から、内部整合性のとれた合成世帯・人口マイクロデータを生成できます
- 生成した合成人口について、**統計整合性・有用性・秘匿性の 3 層**で評価レポートを自動生成できます
- 生成パラメータの改善ループ（rule-based / Pareto）で「使える」合成人口を探索できます

---

## 2. 位置付け — Murata 2017 と Harada 2024 の関係

本プロジェクトは **2 本の論文** を 1 つの Python ツールキットに束ねます。

- **生成側** — Murata et al. (2017): 集計表と Simulated Annealing に基づく合成人口生成。本リポジトリの §11〜§12 仕様の主柱です
- **評価側** — Harada (2024): 仮想都市データに対する有用性（utility）と秘匿性（disclosure risk）の評価軸。特に **ARD（Attribute Risk Distance）** を privacy 層の評価に採用しています

「Murata の生成手法が作った合成人口を、Harada の評価軸でスコアリングし、ループで改善する」 — これが本ツールの中核価値です。詳細は [`docs/spec/spec.md`](docs/spec/spec.md) §5.3 参照。

---

## 3. インストール

Python 3.11 以上と [`uv`](https://docs.astral.sh/uv/) が必要です。

```bash
# グローバルツールとしてインストール
uv tool install synthpop-jp

# または一時的に実行
uvx synthpop-jp --help
```

開発版を clone から動かす場合:

```bash
git clone https://github.com/gghatano/synth-pop-harada-2024.git
cd synth-pop-harada-2024
uv sync --frozen
uv run synthpop-jp --help
```

---

## 4. 30 秒 Quickstart

同梱のダミーデータ（`data/sample_case/`）を使って、合成人口を 10 秒以内に生成できます。

```bash
# clone からすぐ試す場合
git clone https://github.com/gghatano/synth-pop-harada-2024.git
cd synth-pop-harada-2024
uv sync --frozen
uv run synthpop-jp quickstart
```

```bash
# uvx でインストール不要で試す場合
uvx --from git+https://github.com/gghatano/synth-pop-harada-2024.git synthpop-jp quickstart
```

実行すると `outputs/quickstart/` に 3 ファイルが生成されます:

| ファイル | 内容 |
|---|---|
| `synthetic_households.csv` | 合成世帯（household_id, family_type, household_size） |
| `synthetic_persons.csv` | 合成個人（person_id, household_id, family_type, role, sex, age） |
| `metrics.json` | 集計メトリクス（総世帯数・総人数・family_type 別内訳など） |

設定ファイルを事前に検証するには:

```bash
uv run synthpop-jp validate-config configs/base.yaml
# ✓ Config is valid: configs/base.yaml
```

便利なオプション:

```bash
# シードを指定して実行（同じシードなら同じ結果が再現される）
uv run synthpop-jp quickstart --seed 123

# ファイル書き出しをスキップして動作確認のみ
uv run synthpop-jp quickstart --dry-run

# デバッグログを表示
uv run synthpop-jp quickstart --log-level DEBUG
```

e-Stat からの実データ取得は `scripts/fetch_estat.py`（Phase 2 以降で提供予定）を使ってユーザー環境でダウンロードしてください。詳細は `DATASET.md`。

---

## 5. 入出力

入力は「集計表の CSV 群」、出力は「世帯・個人の合成マイクロデータ CSV」です。詳細な列定義・単位・欠損規則は [`docs/spec/spec.md`](docs/spec/spec.md) §7 を参照してください。

**入力（最小構成）**:
- `family_type_counts.csv`（家族類型別世帯数）
- `age_distribution.csv`（年齢階級別人口）
- `household_size_distribution.csv`（世帯サイズ分布）

**出力**:
- `synthetic_households.csv`（合成世帯）
- `synthetic_persons.csv`（合成個人）
- `report.md` / `report.html`（評価レポート、Phase 4 以降）

---

## 6. 類似 OSS との比較

| ツール | データ前提 | 手法 | 本実装との違い |
|---|---|---|---|
| synthpop (R) | サンプル個票必須 | CART / 条件付確率 | 集計表のみで動作 |
| SDV / CTGAN | 表形式データ全般 | GAN / copula | 世帯構造を保存する SA |
| PopulationSim / ActivitySim | 旅客需要 | IPF | 目的関数カスタム可 SA |
| **synthpop-jp** | 公開集計表のみ | SA（Murata 2017） | 国勢調査テンプレ + ARD 評価内蔵 |

**差別化要点**: 日本の国勢調査 / e-Stat テンプレートを標準装備し、Murata 2017 の再現を保証しつつ、Harada 2024 の ARD 評価を内蔵する点が他の OSS に無い特徴です。

---

## 7. 引用

本ソフトウェアを研究で使う場合は以下を引用してください。

**ソフトウェア**: 本リポジトリ同梱の [`CITATION.cff`](CITATION.cff) を参照（GitHub の "Cite this repository" ボタンから BibTeX などを取得できます）。

**論文（生成手法）**: Murata et al. (2017) — Simulated Annealing-based 合成人口生成手法の原典

**論文（評価手法）**: Harada (2024) — 仮想都市データに対する ARD 評価軸

引用の正式書式は `CITATION.cff` の `preferred-citation` と `references` を参照してください（DOI は Phase 0 完了後に正式記入予定）。

---

## 8. ロードマップ（要約）

- **v0.1 (alpha)** — Phase 2 完了時点。`synthpop-jp quickstart` が 10 秒で動く。sample_case ダミー、age-change のみ、日英 README、LICENSE、CITATION.cff、CI 整備済
- **v0.2** — Phase 4 完了時点。age-swap / hybrid、ARD を含む評価、e-Stat adapter、mkdocs サイト、3 本の notebook チュートリアル、SDV 比較表
- **v0.3** — Phase 5 完了時点。改善ループ（rule_based / Pareto）、複数 trial、比較レポート自動生成、plugin entry_points 公開
- **v1.0** — 論文公開と同時。Murata 2017 再現結果を `paper_results/` に固定、Zenodo DOI、CITATION.cff 更新、英語ドキュメント完備

詳細は [`docs/reviews/action-plan.md`](docs/reviews/action-plan.md) §3 および [`docs/spec/spec.md`](docs/spec/spec.md) §16。

---

## 9. コントリビューション

歓迎します。開発環境のセットアップ、Issue 駆動フロー、ブランチ / worktree 配置規約、新 family_type / 評価器の追加手順は [`CONTRIBUTING.md`](CONTRIBUTING.md) にまとめています。

行動規範は [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md)（Contributor Covenant v2.1）を採用しています。

---

## 10. ライセンス

[Apache License 2.0](LICENSE)。依存ライブラリのクレジット骨子は [`NOTICE`](NOTICE) を参照（Phase 1 で `uv.lock` から自動生成に更新）。

データの取り扱い（e-Stat 再配布ポリシー、合成ダミーの扱い、統計法 §44 への対応）は [`DATASET.md`](DATASET.md) を参照してください。
