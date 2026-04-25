# HTML レポート運用ルール

実験結果を **誰でも 1 クリックで読める** 形で保存することを目的に、HTML レポートの運用ルールを定めます。
Markdown で書いた実験レポートを HTML に変換し、Issue / PR から参照できる状態を維持します。

---

## 1. 目的

- Markdown だけだと図が表示されない環境がある（メール添付・古いビューアー）
- 非技術者のレビュアーが、ツール不要で開ける形式が必要
- 実験結果のスナップショットを **後から変化しない形** で保存したい
- Issue / PR / レポートの相互参照を、URL ベースで安定させたい

---

## 2. 配置ルール

HTML は Markdown の **同じディレクトリ** に並べて置きます。

```
experiments/
  2026-04-23-sa-convergence-baseline/
    report.md              # 編集する実体
    report.html            # report.md を変換した結果（コミット対象）
    config.yaml
    data/INPUT.md
    output/
      figures/*.png        # HTML から相対パスで参照
      metrics/*.csv
```

- HTML は自動生成物だが、**リポジトリにコミットする**（閲覧のために残す）
- 画像・CSV は `output/` 配下。HTML からは相対パスで参照する
- Markdown と HTML のファイル名は対応させる（`report.md` ↔ `report.html`）

---

## 3. ファイル命名規則

| 種類 | 名前 |
|---|---|
| 主レポート | `report.md` / `report.html` |
| 複数レポートに分ける場合 | `report-<サブ観点>.md` / `.html`（例: `report-convergence.md`） |
| 実験ディレクトリ名 | `<YYYY-MM-DD>-<slug>`（例: `2026-04-23-sa-convergence-baseline`） |

レポート名は日付や Issue 番号を含めない。日付と Issue 番号は **ディレクトリ名** と **レポート冒頭のメタデータ** で表現します（同じ情報を 2 箇所に書かない）。

---

## 4. レポートの必須セクション

すべての HTML レポートは以下の構成を持つことを必須にします（雛形: [`docs/templates/experiment_report.md`](../templates/experiment_report.md)）。

| セクション | 役割 |
|---|---|
| 1. 非技術者向け要約 | 実験の目的・結果・含意を 4〜5 行で。専門用語は避けるか補足を添える |
| 2. 技術詳細 | 条件、評価指標、数値結果、図 |
| 3. 解釈 | 結果が仮説を支持したか。どう解釈するか |
| 4. 制約 | 結果を一般化できない範囲、サンプル限界 |
| 5. 再現手順 | 1 コマンドで走る形。seed と config のパスを明示 |
| 6. 次に見るべき論点 | 追加実験、関連 Issue、未解決の疑問 |

非技術者向け要約（1）を必ず **最上段** に置きます。レビュアーが最初に読むのはこの 5 行だけだと考えて書く。

---

## 5. HTML レポートの生成方針（Phase 1 以降確定）

Phase 1 の Issue #38 で HTML 生成パイプラインが実装された（`src/synthpop_jp/reports/`）。
Pandoc・Quarto への依存なしに、Python 単体で self-contained HTML を生成できる。

### 5.1 基本的な使い方

```python
import json
import pandas as pd
from pathlib import Path
from synthpop_jp.reports.html import generate_html_report

data = {
    "households": pd.read_csv("outputs/quickstart/synthetic_households.csv"),
    "persons": pd.read_csv("outputs/quickstart/synthetic_persons.csv"),
    "metrics": json.loads(Path("outputs/quickstart/metrics.json").read_text()),
}
generate_html_report(
    data,
    "experiments/<日付>-<slug>/report.html",
    template_vars={"title": "レポートタイトル"},
)
```

### 5.2 技術仕様

| 項目 | 仕様 |
|---|---|
| plotly | `to_html(include_plotlyjs="inline")` でインライン埋め込み |
| CSS | `<style>` タグ内インライン（外部ファイル不要） |
| ファイルサイズ | plotly inline JS（約 4.7 MB）を含む。CDN 版は 10 KB 未満だが self-contained でなくなる |
| 外部依存 | ゼロ（ブラウザだけで開ける） |

### 5.3 将来の CLI 化

`synthpop-jp report` サブコマンドへの統合は別 Issue で対応予定。
現在は Python API として直接呼び出す。

---

## 5a. 非技術者向け文体ガイド

経営層（完全非技術者）がレポートを 30 秒で理解できるよう、以下の文体を守る。
`docs/rules/documentation-style.md` の全体ガイドと整合させること。

### 5a.1 要約の書き方（冒頭 5 行の原則）

要約セクションは **「今何が分かったか」** と **「次に何を決めたいか」** の 2 軸で書く。

良い例:
> 合成人口（統計に合わせて人工的に作成した個票データ）を生成しました。
> 100 世帯のダミー入力から 266 人分のデータを出力しました。
> 最も多い家族構成は「夫婦と子ども」（30%）です。
> SA 最適化（徐々に統計に近づける手法）は Phase 2 で実施します。
> 次のステップでは年齢分布の精度を改善します。

悪い例:
> quickstart を実行して合成人口を生成した。metrics.json を確認すると 266 人だった。

差異:
- 良い例は「誰に何が分かるか」を先に書いている
- 専門用語（合成人口、SA）に括弧補足がある
- 悪い例は実装者の作業メモになっており、非技術者には意味が分からない

### 5a.2 1 文の長さ

| ルール | 目安 |
|---|---|
| 1 文の字数 | 30〜40 字（最長 60 字以内） |
| 段落の文数 | 1 段落に 2〜3 文まで |
| 専門用語 | 初出に括弧補足を付ける |

### 5a.3 CSS 設計の指針

非技術者向け HTML レポートの CSS は以下を守る:
- フォントサイズ: `1.1rem` 以上（デフォルト 16px の 1.1 倍 = 約 17.6px）
- 要約セクション: 背景色（黄色系）+ 太字 + 左ボーダーで視覚的に目立たせる
- カラーパレット: 高コントラスト、柔らかい色調（`#4E79A7`, `#E15759` 等）
- 外部フォントや CDN を使わない（self-contained 維持）

実装例: `src/synthpop_jp/reports/html.py` の `_CSS` 定数を参照。

---

## 6. Issue / PR との相互リンク

| 方向 | 何を書くか |
|---|---|
| Issue → HTML | Issue 本文 or コメントに `experiments/<日付>-<slug>/report.html` へのリンク |
| HTML → Issue | レポート冒頭に `Issue: #<番号>` の行 |
| PR → HTML | PR 本文の「実験 / 検証」欄に HTML リンク |
| HTML → PR | レポート冒頭に `PR: #<番号>` の行（merge 後に追記） |

このうち **HTML → Issue** のリンクは実験開始時から必ずあること。他は作業の進行に応じて追加します。

---

## 7. 公開場所

- 開発中は GitHub 上のリポジトリ内ファイルとして閲覧（`github.com/.../experiments/.../report.html` を raw で見る、もしくは HTML preview 拡張）
- 将来的に GitHub Pages / 社内ホスティングにデプロイする場合、デプロイコマンドを `Makefile` / `justfile` に追加する
- **外部公開は慎重に**: レポート内にデータの一部が含まれると個人情報漏洩リスクがある。外部に出す前に `docs/spec/metrics.md` や privacy レビュー観点で確認

---

## 8. 更新ポリシー

- 実験レポートは **追記型**。一度コミットした結果を書き換えない
- 誤記・誤植の修正は OK。ただし数値結果を書き換える場合は別ディレクトリで新実験として記録する
- レポート内の「解釈」欄は、新しい知見が得られた時点で追記してよい（日付付き）
  - 例: `## 追記（2026-05-10）: 追試 #123 により本結果は一般化できないと判明`

---

## 9. チェックリスト

### レポート作成時
- [ ] 非技術者向け要約（5 行以内）が最上段にある
- [ ] 冒頭に Issue 番号・ブランチ名・コミット SHA がある
- [ ] 再現手順が 1 コマンド形式で書かれている
- [ ] 制約・次アクションが書かれている

### HTML 化時
- [ ] `report.md` と同じディレクトリに `report.html` がある
- [ ] 図・CSV が相対パスで正しく参照できる
- [ ] Issue / PR に HTML リンクを追加した
