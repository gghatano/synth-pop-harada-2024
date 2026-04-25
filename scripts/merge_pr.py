"""merge_pr.py — make merge-pr の実体スクリプト.

PM が `make merge-pr PR=N [DRY_RUN=1]` で呼ぶ。
7 ステップで PR の ready → merge → worktree 削除 → develop 同期を完結させる。

使い方::

    uv run python scripts/merge_pr.py --pr 48
    uv run python scripts/merge_pr.py --pr 48 --dry-run
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# 内部ヘルパー（patch ポイント）
# ---------------------------------------------------------------------------


def _run_cmd(
    args: list[str],
    cwd: str | None = None,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Subprocess.run のラッパー。テストで patch するためのポイント."""
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        cwd=cwd,
        check=check,
    )


# ---------------------------------------------------------------------------
# 純粋関数: branch → worktree path 変換
# ---------------------------------------------------------------------------


def branch_to_worktree_path(branch_name: str, repo_root: str) -> str | None:
    """ブランチ名から worktree path を導出する.

    変換ルール:
      feature/48-merge-pr-helper → <repo_root>/gitworktree/feature-48-merge-pr-helper

    feature/ で始まらないブランチは None を返す。

    Parameters
    ----------
    branch_name:
        GitHub PR の headRefName（例: feature/48-merge-pr-helper）
    repo_root:
        リポジトリルートの絶対パス

    Returns
    -------
    str | None
        worktree の絶対パス文字列。feature/ ブランチでなければ None。
    """
    if not branch_name.startswith("feature/"):
        return None
    # feature/48-merge-pr-helper → feature-48-merge-pr-helper
    worktree_dir_name = branch_name.replace("/", "-", 1)
    return str(Path(repo_root) / "gitworktree" / worktree_dir_name)


# ---------------------------------------------------------------------------
# 純粋関数: PR 状態の解析
# ---------------------------------------------------------------------------


def check_pr_status(
    pr_data: dict[str, Any],
) -> tuple[str, str, str]:
    """PR の JSON データから状態を解析する.

    PR データは gh pr view --json state,mergeable,headRefName,statusCheckRollup
    の出力を想定する。

    Parameters
    ----------
    pr_data:
        gh pr view の JSON パース結果

    Returns
    -------
    tuple[str, str, str]
        (status, state, head_ref) のタプル。
        status は以下のいずれか:

        - "ok": merge 可能
        - "already_merged": 既に merge 済み（no-op でよい）
        - "ci_failed": CI が失敗している
        - "error": CLOSED など処理不能な状態
    """
    state: str = pr_data.get("state", "")
    head_ref: str = pr_data.get("headRefName", "")
    status_checks: list[dict[str, Any]] = pr_data.get("statusCheckRollup", [])

    if state == "MERGED":
        return "already_merged", state, head_ref

    if state != "OPEN":
        return "error", state, head_ref

    # CI チェックが存在する場合、最後の状態が SUCCESS でなければ失敗
    if status_checks:
        last_status = status_checks[-1].get("state", "")
        if last_status != "SUCCESS":
            return "ci_failed", state, head_ref

    return "ok", state, head_ref


# ---------------------------------------------------------------------------
# メイン処理
# ---------------------------------------------------------------------------


def merge_pr(
    pr_number: int,
    dry_run: bool = False,
    repo_root: str | None = None,
) -> int:
    """PR を merge して worktree を片付ける.

    7 ステップで実行:

    1. PR 状態確認
    2. gh pr ready（Draft → Ready）
    3. gh pr merge --squash --delete-branch
    4. headRefName 取得（ステップ 1 で取得済み）
    5. branch → worktree path 変換
    6. git worktree remove
    7. git branch -D
    8. git checkout develop && git pull --ff-only

    Parameters
    ----------
    pr_number:
        マージ対象の PR 番号
    dry_run:
        True のとき実際のコマンドを実行しない（ステップを表示するのみ）
    repo_root:
        リポジトリルートのパス。None の場合は git rev-parse で取得

    Returns
    -------
    int
        終了コード。0 = 成功、1 = エラー
    """
    # repo_root を解決
    if repo_root is None:
        result = _run_cmd(["git", "rev-parse", "--show-toplevel"])
        repo_root = result.stdout.strip()

    pr_str = str(pr_number)

    # -----------------------------------------------------------------------
    # ステップ 1: PR 状態確認
    # -----------------------------------------------------------------------
    print(f"[merge-pr] Step 1: PR #{pr_number} の状態を確認中...")
    view_result = _run_cmd(
        [
            "gh",
            "pr",
            "view",
            pr_str,
            "--json",
            "state,mergeable,headRefName,statusCheckRollup",
        ],
        cwd=repo_root,
    )
    if view_result.returncode != 0:
        print(
            f"[merge-pr] ERROR: gh pr view に失敗しました: {view_result.stderr}",
            file=sys.stderr,
        )
        return 1

    try:
        pr_data: dict[str, Any] = json.loads(view_result.stdout)
    except json.JSONDecodeError as e:
        print(f"[merge-pr] ERROR: gh pr view の JSON パースに失敗: {e}", file=sys.stderr)
        return 1

    status, state, head_ref = check_pr_status(pr_data)

    if status == "already_merged":
        print(
            f"[merge-pr] WARNING: PR #{pr_number} は既に merged です。"
            "worktree 片付けのみ実施します。"
        )
        # worktree 片付けだけ行う（merge はスキップ）
        _cleanup_worktree(head_ref, repo_root, dry_run)
        _sync_develop(repo_root, dry_run)
        return 0

    if status == "ci_failed":
        print(
            f"[merge-pr] ERROR: PR #{pr_number} の CI が SUCCESS ではありません"
            f"（state={state}）。強制 merge を防ぐため中断します。",
            file=sys.stderr,
        )
        return 1

    if status == "error":
        print(
            f"[merge-pr] ERROR: PR #{pr_number} の state={state} は処理できません"
            "（OPEN or MERGED のみ）。",
            file=sys.stderr,
        )
        return 1

    # status == "ok"
    print(f"[merge-pr] PR #{pr_number} は state={state}, CI=OK。merge を実行します。")

    # -----------------------------------------------------------------------
    # ステップ 2: gh pr ready（Draft → Ready）
    # -----------------------------------------------------------------------
    print(f"[merge-pr] Step 2: gh pr ready #{pr_number}...")
    if dry_run:
        print(f"  [DRY-RUN] gh pr ready {pr_str}")
    else:
        # Draft でない場合は no-op でエラーになることがあるが無視
        _run_cmd(["gh", "pr", "ready", pr_str], cwd=repo_root)

    # -----------------------------------------------------------------------
    # ステップ 3: gh pr merge --squash --delete-branch
    # -----------------------------------------------------------------------
    print(f"[merge-pr] Step 3: gh pr merge #{pr_number} --squash --delete-branch...")
    if dry_run:
        print(f"  [DRY-RUN] gh pr merge {pr_str} --squash --delete-branch")
    else:
        merge_result = _run_cmd(
            ["gh", "pr", "merge", pr_str, "--squash", "--delete-branch"],
            cwd=repo_root,
        )
        if merge_result.returncode != 0:
            print(
                f"[merge-pr] ERROR: gh pr merge に失敗しました: {merge_result.stderr}",
                file=sys.stderr,
            )
            return 1

    # -----------------------------------------------------------------------
    # ステップ 4-7: worktree 片付け
    # -----------------------------------------------------------------------
    _cleanup_worktree(head_ref, repo_root, dry_run)

    # -----------------------------------------------------------------------
    # ステップ 8: develop を最新化
    # -----------------------------------------------------------------------
    _sync_develop(repo_root, dry_run)

    print(f"[merge-pr] 完了: PR #{pr_number} を merge し、worktree を片付けました。")
    return 0


def _cleanup_worktree(
    head_ref: str,
    repo_root: str,
    dry_run: bool,
) -> None:
    """Worktree と local branch を削除する（ステップ 5-7）.

    worktree や branch が存在しない場合は WARNING を出して続行する。
    """
    # ステップ 5: branch → worktree path 変換
    worktree_path = branch_to_worktree_path(head_ref, repo_root)

    # ステップ 6: git worktree remove
    if worktree_path:
        print(f"[merge-pr] Step 6: git worktree remove {worktree_path}...")
        if dry_run:
            print(f"  [DRY-RUN] git worktree remove {worktree_path}")
        else:
            rm_result = _run_cmd(
                ["git", "worktree", "remove", worktree_path],
                cwd=repo_root,
            )
            if rm_result.returncode != 0:
                print(
                    "[merge-pr] WARNING: worktree remove に失敗しました（不在の可能性）: "
                    f"{rm_result.stderr}",
                )
    else:
        print(
            f"[merge-pr] Step 6: worktree path を導出できませんでした"
            f"（branch={head_ref}）。スキップ。"
        )

    # ステップ 7: git branch -D
    print(f"[merge-pr] Step 7: git branch -D {head_ref}...")
    if dry_run:
        print(f"  [DRY-RUN] git branch -D {head_ref}")
    else:
        branch_result = _run_cmd(
            ["git", "branch", "-D", head_ref],
            cwd=repo_root,
        )
        if branch_result.returncode != 0:
            print(
                "[merge-pr] WARNING: branch -D に失敗しました（不在の可能性）: "
                f"{branch_result.stderr}",
            )


def _sync_develop(repo_root: str, dry_run: bool) -> None:
    """Develop ブランチを最新化する（ステップ 8）."""
    print("[merge-pr] Step 8: develop を最新化中...")
    if dry_run:
        print("  [DRY-RUN] git checkout develop")
        print("  [DRY-RUN] git pull --ff-only")
    else:
        _run_cmd(["git", "checkout", "develop"], cwd=repo_root)
        _run_cmd(["git", "pull", "--ff-only"], cwd=repo_root)


# ---------------------------------------------------------------------------
# CLI エントリーポイント
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """コマンドライン引数をパースする."""
    parser = argparse.ArgumentParser(description="PR を merge して worktree を片付ける。")
    parser.add_argument(
        "--pr",
        type=int,
        required=True,
        help="merge 対象の PR 番号",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="コマンドを実行せず手順を表示するだけ",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """CLI エントリーポイント."""
    args = _parse_args(argv)
    exit_code = merge_pr(pr_number=args.pr, dry_run=args.dry_run)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
