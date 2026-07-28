# 論文再現の敵対的検証とクロスプラットフォーム課題の修正

- 日付: 2026-07-29
- ブランチ: `feature/windows-portability`
- コミット: `6228b7f`
- Issue: （未起票 — 探索的検証セッション）
- 環境: Windows 11 / Python 3.12 (uv) / pytest 8

---

## 1. 非技術者向け要約

論文の実験結果（合成人口を作る手法の再現）が「本当に正しく再現できているか」を、結果を疑う立場から検証しました。
4つの再現実験はすべて合格し、生成データは基準値と1バイトも違わず完全一致しました（近いだけではなく厳密に一致）。
一方で、検証をリポジトリ全体に広げると、Windows 環境でテスト11件が失敗していることを発見しました。
原因はWindowsとLinuxのファイルパスの違いなど「動く環境が限られる」不具合で、3点を修正し全テストを合格（0失敗）にしました。
論文再現の数値には一切影響していません。

---

## 2. 技術詳細

### 2.1 論文再現（paper_results 全4実験）

固定 seed で 4 実験を実行し、コミット済みの期待値CSVと許容幅（best_score ±1% / utility ±5%）で照合した。

| 実験 | 内容 | tolerance判定 |
|---|---|---|
| exp01 | age-change vs age-swap | PASS |
| exp02 | hybrid 戦略比較 | PASS |
| exp03 | 改善ループ3戦略（rule_based / pareto / random_search） | PASS |
| exp04 | 複数候補ばらつき（CV + bootstrap 95% CI） | PASS |

### 2.2 敵対的検証（"PASS を疑う"）

| 疑い | 検証方法 | 結果 |
|---|---|---|
| tolerance が実質ザルでは | 実装読解（構造・文字列一致・相対差分） | 妥当。ザルではない |
| 今の結果を自己比較して常時PASSでは | run.py 読解 | 比較対象はコミット済み `expected/`、生成物は gitignore の `outputs/`。自己比較ではない |
| 基準を実行が汚したのでは | `git status` | クリーン。`expected/` 無改変 |
| チェックは本当にFAILできるか | 453→500（10%ずれ）に改竄した入力を投入 | FAIL 検出・exit 1 を確認 |
| 「±1%以内」で近いだけでは | 生成物と `expected/` を `diff` | 全ファイル**バイト完全一致（0%差）** |
| 期待値ファイルの黙殺は | expected/ と outputs/ のファイル集合を突合 | 全ファイル比較済み。黙殺なし |

### 2.3 発見・修正した課題

CI parity（lint / format / type / test）をリポジトリ全体に流したところ、pytest で 11 件失敗。

| 課題 | 種別 | 修正 |
|---|---|---|
| `merge_pr.branch_to_worktree_path` が Windows で `\` 区切りを返し、`git worktree remove` 用の値が OS 依存（3件失敗） | 実コードの移植性バグ | `/` 区切り明示結合＋バックスラッシュ正規化。未使用 `Path` import 除去 |
| `test_make_targets.py` が `make` 未導入環境で `FileNotFoundError`（7件失敗） | テストの移植性 | `shutil.which("make")` で skip 判定。CI(Linux) では従来通り実行 |
| `py.typed` 未同梱で pyright 警告377件 | パッケージング漏れ | PEP 561 マーカー追加。wheel 同梱をビルドで実証 |

### 2.4 対応後の検証結果

| 項目 | 修正前 | 修正後 |
|---|---|---|
| pytest | 776 passed / 11 failed / 10 skipped | 779 passed / **0 failed** / 18 skipped |
| ruff check / format | クリーン | クリーン |
| pyright | 0 errors / 377 warnings | 0 errors / **19 warnings**（残は外部ライブラリ由来） |
| paper_results 4実験 | PASS | PASS（影響なし） |

---

## 3. 解釈

論文再現の主張は「決定的（deterministic）かつバイト単位で再現可能」という強い形で裏付けられた。
tolerance チェックは改竄入力を正しく FAIL させるため、合否判定の信頼性も確認できた。
発見した課題はいずれも「Windows で動かすと顕在化する移植性の問題」であり、生成・評価アルゴリズム本体の正しさとは独立している。

---

## 4. 制約

- 検証は CI 既定設定（100世帯 / 3 seed / 2水準）に対するもの。フル設定（1000世帯）は別途 `--full` で要検証。
- Windows 環境1台での実測。macOS 等での再検証は未実施。
- pyright 残19警告は pandas / scipy / plotly のスタブ欠如で当リポジトリでは解消不能。
- 本セッションはIssue未起票の探索的検証で、リポジトリ規約（Issue駆動・worktree・TDD）の一部を省略している。

---

## 5. 再現手順

```bash
uv sync --frozen --all-groups

# 論文再現（全4実験、固定seed）
PYTHONPATH=. uv run python paper_results/experiment-01-age-change-vs-age-swap/run.py --check-tolerance
PYTHONPATH=. uv run python paper_results/experiment-02-hybrid-strategy/run.py --check-tolerance
PYTHONPATH=. uv run python paper_results/experiment-03-improve-strategy-comparison/run.py --check-tolerance
PYTHONPATH=. uv run python paper_results/experiment-04-multi-trial-variance/run.py --check-tolerance

# 敵対的検証: tolerance が改竄を FAIL させるか
cp paper_results/experiment-01-age-change-vs-age-swap/expected/best_scores.csv /tmp/t.csv
sed -i 's/,453.0/,500.0/g' /tmp/t.csv
PYTHONPATH=. uv run python -m paper_results._shared.tolerance_check /tmp/t.csv \
  paper_results/experiment-01-age-change-vs-age-swap/expected/best_scores.csv   # -> exit 1

# CI parity
uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest -n auto -q
```

---

## 6. 次に見るべき論点

- `--full`（1000世帯）設定での再現一致確認（別タイムスロット）。
- mkdocs の壊れた相対リンク警告（docs_dir 外参照）の整理 — 本セッションではスコープ外として見送り。
- quickstart の Windows コンソール文字化け（cp932 表示アーティファクト。データ自体は正しい UTF-8）。
- 本修正の正式取り込み: Issue 起票 → develop 向け PR 化。
