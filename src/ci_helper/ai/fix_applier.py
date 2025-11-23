"""自動修正適用機能

AI生成の修正提案を安全に適用し、バックアップ作成と検証を行います。
"""

from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console

from ..utils.config import Config
from .exceptions import AIError
from .models import CodeChange, FixSuggestion, FixTemplate, PatternMatch

logger = logging.getLogger(__name__)
console = Console()


class FixApprovalResult:
    """修正承認結果"""

    def __init__(self, approved: bool, reason: str = ""):
        self.approved = approved
        self.reason = reason
        self.timestamp = datetime.now()


class BackupManager:
    """バックアップ管理クラス"""

    def __init__(self, backup_dir: Path):
        self.backup_dir = backup_dir
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create_backup(self, file_path: Path) -> Path:
        """ファイルのバックアップを作成

        Args:
            file_path: バックアップ対象のファイルパス

        Returns:
            バックアップファイルのパス

        Raises:
            AIError: バックアップ作成に失敗した場合

        """
        if not file_path.exists():
            raise AIError(f"バックアップ対象ファイルが存在しません: {file_path}")

        # タイムスタンプ付きのバックアップファイル名を生成
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.name}.{timestamp}.backup"
        backup_path = self.backup_dir / backup_name

        try:
            shutil.copy2(file_path, backup_path)
            logger.info("バックアップを作成しました: %s -> %s", file_path, backup_path)
            return backup_path
        except Exception as e:
            raise AIError(f"バックアップの作成に失敗しました: {e}") from e

    def restore_backup(self, original_path: Path, backup_path: Path) -> None:
        """バックアップからファイルを復元

        Args:
            original_path: 復元先のファイルパス
            backup_path: バックアップファイルのパス

        Raises:
            AIError: 復元に失敗した場合

        """
        if not backup_path.exists():
            raise AIError(f"バックアップファイルが存在しません: {backup_path}")

        try:
            shutil.copy2(backup_path, original_path)
            logger.info("バックアップから復元しました: %s -> %s", backup_path, original_path)
        except Exception as e:
            raise AIError(f"バックアップからの復元に失敗しました: {e}") from e

    def list_backups(self, file_pattern: str | None = None) -> list[Path]:
        """バックアップファイル一覧を取得

        Args:
            file_pattern: ファイル名パターン（省略時は全て）

        Returns:
            バックアップファイルパスのリスト

        """
        if file_pattern:
            return list(self.backup_dir.glob(f"{file_pattern}.*.backup"))
        return list(self.backup_dir.glob("*.backup"))

    def cleanup_old_backups(self, keep_count: int = 10) -> None:
        """古いバックアップを削除

        Args:
            keep_count: 保持するバックアップ数

        """
        backups = sorted(self.backup_dir.glob("*.backup"), key=lambda p: p.stat().st_mtime, reverse=True)

        for backup in backups[keep_count:]:
            try:
                backup.unlink()
                logger.debug("古いバックアップを削除: %s", backup)
            except Exception as e:
                logger.warning("バックアップの削除に失敗: %s", e)


class FixApplier:
    """修正適用クラス

    AI生成の修正提案を安全に適用し、バックアップと検証を行います。
    """

    def __init__(self, config: Config, interactive: bool = True):
        """修正適用器を初期化

        Args:
            config: 設定オブジェクト
            interactive: 対話モード（承認を求めるかどうか）

        """
        self.config = config
        self.interactive = interactive
        self.project_root = Path.cwd()

        # バックアップディレクトリを設定
        backup_dir = config.get_path("cache_dir") / "backups"
        self.backup_manager = BackupManager(backup_dir)

        # 適用結果を記録
        self.applied_fixes: list[dict[str, Any]] = []
        self.failed_fixes: list[dict[str, Any]] = []

    def apply_fix_suggestions(self, fix_suggestions: list[FixSuggestion], auto_approve: bool = False) -> dict[str, Any]:
        """修正提案を適用

        Args:
            fix_suggestions: 修正提案のリスト
            auto_approve: 自動承認フラグ

        Returns:
            適用結果の辞書

        """
        logger.info("修正提案の適用を開始 (提案数: %d)", len(fix_suggestions))

        results = {
            "total_suggestions": len(fix_suggestions),
            "applied_count": 0,
            "skipped_count": 0,
            "failed_count": 0,
            "applied_fixes": [],
            "failed_fixes": [],
            "backups_created": [],
        }

        for i, suggestion in enumerate(fix_suggestions, 1):
            logger.info("修正提案 %d/%d を処理中: %s", i, len(fix_suggestions), suggestion.title)

            try:
                # 承認を確認
                if not auto_approve and self.interactive:
                    approval = self._request_approval(suggestion)
                    if not approval.approved:
                        logger.info("修正提案をスキップ: %s", approval.reason)
                        results["skipped_count"] += 1
                        continue

                # 修正を適用
                apply_result = self._apply_single_fix(suggestion)

                if apply_result["success"]:
                    results["applied_count"] += 1
                    results["applied_fixes"].append(apply_result)
                    results["backups_created"].extend(apply_result.get("backups", []))
                    logger.info("修正提案を適用しました: %s", suggestion.title)
                else:
                    results["failed_count"] += 1
                    results["failed_fixes"].append(apply_result)
                    logger.error("修正提案の適用に失敗: %s", apply_result.get("error", "不明なエラー"))

            except Exception as e:
                logger.error("修正提案の処理中にエラー: %s", e)
                results["failed_count"] += 1
                results["failed_fixes"].append({"suggestion": suggestion.title, "error": str(e), "success": False})

        logger.info(
            "修正適用完了 - 適用: %d, スキップ: %d, 失敗: %d",
            results["applied_count"],
            results["skipped_count"],
            results["failed_count"],
        )

        return results

    # エイリアスを追加
    apply_fix = apply_fix_suggestions

    def _request_approval(self, suggestion: FixSuggestion) -> FixApprovalResult:
        """修正提案の承認を要求

        Args:
            suggestion: 修正提案

        Returns:
            承認結果

        """
        if suggestion.code_changes:
            for _i, change in enumerate(suggestion.code_changes, 1):
                # 変更内容のプレビュー
                if change.old_code and change.new_code:
                    pass

        while True:
            try:
                response = (
                    input("この修正を適用しますか? [y/n/s/q] (y=はい, n=いいえ, s=スキップ, q=終了): ").lower().strip()
                )

                if response in ["y", "yes"]:
                    return FixApprovalResult(True, "ユーザーが承認")
                if response in ["n", "no"]:
                    return FixApprovalResult(False, "ユーザーが拒否")
                if response in ["s", "skip"]:
                    return FixApprovalResult(False, "ユーザーがスキップ")
                if response in ["q", "quit"]:
                    raise KeyboardInterrupt("ユーザーが終了を選択")

            except KeyboardInterrupt:
                return FixApprovalResult(False, "ユーザーが中断")
            except EOFError:
                return FixApprovalResult(False, "入力エラー")

    def _apply_single_fix(self, suggestion: FixSuggestion) -> dict[str, Any]:
        """単一の修正提案を適用

        Args:
            suggestion: 修正提案

        Returns:
            適用結果の辞書

        """
        result = {"suggestion": suggestion.title, "success": False, "backups": [], "applied_changes": [], "error": None}

        try:
            # コード変更を適用
            for change in suggestion.code_changes:
                change_result = self._apply_code_change(change)

                if change_result["success"]:
                    result["applied_changes"].append(change_result)
                    if change_result.get("backup_path"):
                        result["backups"].append(str(change_result["backup_path"]))
                else:
                    # 一つでも失敗したら全体を失敗とする
                    result["error"] = change_result.get("error", "コード変更の適用に失敗")
                    return result

            # 修正後の検証
            validation_result = self._validate_fix(suggestion)
            if not validation_result["valid"]:
                result["error"] = f"修正後の検証に失敗: {validation_result.get('error', '不明なエラー')}"
                return result

            result["success"] = True
            self.applied_fixes.append({"suggestion": suggestion, "timestamp": datetime.now(), "result": result})

        except Exception as e:
            result["error"] = str(e)
            self.failed_fixes.append({"suggestion": suggestion, "timestamp": datetime.now(), "error": str(e)})

        return result

    def _apply_code_change(self, change: CodeChange) -> dict[str, Any]:
        """コード変更を適用

        Args:
            change: コード変更

        Returns:
            変更適用結果の辞書

        """
        result = {"file_path": change.file_path, "success": False, "backup_path": None, "error": None}

        try:
            file_path = self.project_root / change.file_path

            # ファイルが存在しない場合は新規作成
            if not file_path.exists():
                logger.info("新規ファイルを作成: %s", file_path)
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(change.new_code, encoding="utf-8")
                result["success"] = True
                return result

            # バックアップを作成
            backup_path = self.backup_manager.create_backup(file_path)
            result["backup_path"] = backup_path

            # ファイル内容を読み込み
            content = file_path.read_text(encoding="utf-8")
            lines = content.splitlines()

            # 行番号の調整（1ベースから0ベースに）
            start_idx = max(0, change.line_start - 1)
            end_idx = min(len(lines), change.line_end)

            # 変更前のコードが一致するかチェック
            if change.old_code.strip():
                existing_code = "\n".join(lines[start_idx:end_idx])
                if change.old_code.strip() not in existing_code:
                    logger.warning(
                        "変更前のコードが一致しません。ファイル: %s, 行: %d-%d",
                        change.file_path,
                        change.line_start,
                        change.line_end,
                    )
                    # 厳密なマッチングを要求しない（AIの提案は完全ではない可能性があるため）

            # コードを置換
            new_lines = lines[:start_idx] + change.new_code.splitlines() + lines[end_idx:]
            new_content = "\n".join(new_lines)

            # ファイルに書き込み
            file_path.write_text(new_content, encoding="utf-8")

            result["success"] = True
            logger.info("コード変更を適用: %s (行 %d-%d)", change.file_path, change.line_start, change.line_end)

        except Exception as e:
            result["error"] = str(e)
            logger.error("コード変更の適用に失敗: %s", e)

        return result

    def _validate_fix(self, suggestion: FixSuggestion) -> dict[str, Any]:
        """修正後の検証を実行

        Args:
            suggestion: 修正提案

        Returns:
            検証結果の辞書

        """
        result = {"valid": True, "checks": [], "error": None}

        try:
            # 基本的な検証
            for change in suggestion.code_changes:
                file_path = self.project_root / change.file_path

                # ファイルの存在確認
                if not file_path.exists():
                    result["valid"] = False
                    result["error"] = f"修正後にファイルが存在しません: {change.file_path}"
                    return result

                # ファイルの読み込み可能性確認
                try:
                    file_path.read_text(encoding="utf-8")
                    result["checks"].append(f"ファイル読み込み OK: {change.file_path}")
                except Exception as e:
                    result["valid"] = False
                    result["error"] = f"修正後のファイルが読み込めません: {change.file_path} - {e}"
                    return result

            # 構文チェック（Python ファイルの場合）
            for change in suggestion.code_changes:
                if change.file_path.endswith(".py"):
                    syntax_check = self._check_python_syntax(change.file_path)
                    result["checks"].append(syntax_check)
                    if not syntax_check.startswith("構文 OK"):
                        result["valid"] = False
                        result["error"] = syntax_check
                        return result

            logger.info("修正後の検証が完了: %s", suggestion.title)

        except Exception as e:
            result["valid"] = False
            result["error"] = str(e)
            logger.error("修正後の検証に失敗: %s", e)

        return result

    def _check_python_syntax(self, file_path: str) -> str:
        """Python ファイルの構文チェック

        Args:
            file_path: ファイルパス

        Returns:
            チェック結果メッセージ

        """
        try:
            full_path = self.project_root / file_path
            content = full_path.read_text(encoding="utf-8")

            # 構文チェック
            compile(content, file_path, "exec")
            return f"構文 OK: {file_path}"

        except SyntaxError as e:
            return f"構文エラー: {file_path} - 行 {e.lineno}: {e.msg}"
        except Exception as e:
            return f"構文チェック失敗: {file_path} - {e}"

    def rollback_fixes(self, backup_paths: list[str]) -> dict[str, Any]:
        """修正をロールバック

        Args:
            backup_paths: バックアップファイルパスのリスト

        Returns:
            ロールバック結果の辞書

        """
        logger.info("修正のロールバックを開始 (バックアップ数: %d)", len(backup_paths))

        result = {
            "total_backups": len(backup_paths),
            "restored_count": 0,
            "failed_count": 0,
            "restored_files": [],
            "failed_files": [],
        }

        for backup_path_str in backup_paths:
            try:
                backup_path = Path(backup_path_str)

                # 元のファイルパスを推定（.timestamp.backup を除去）
                name_parts = backup_path.name.split(".")
                if len(name_parts) >= 3 and name_parts[-1] == "backup":
                    # test.txt.20241018_171837.backup -> test.txt
                    original_name = ".".join(name_parts[:-2])
                else:
                    # フォールバック
                    original_name = name_parts[0]
                original_path = self.project_root / original_name

                # バックアップから復元
                self.backup_manager.restore_backup(original_path, backup_path)

                result["restored_count"] += 1
                result["restored_files"].append(str(original_path))

            except Exception as e:
                logger.error("ロールバックに失敗: %s - %s", backup_path_str, e)
                result["failed_count"] += 1
                result["failed_files"].append({"backup_path": backup_path_str, "error": str(e)})

        logger.info("ロールバック完了 - 復元: %d, 失敗: %d", result["restored_count"], result["failed_count"])

        return result

    def get_apply_summary(self) -> dict[str, Any]:
        """適用結果のサマリーを取得

        Returns:
            適用結果サマリーの辞書

        """
        return {
            "applied_fixes_count": len(self.applied_fixes),
            "failed_fixes_count": len(self.failed_fixes),
            "applied_fixes": [
                {
                    "title": fix["suggestion"].title,
                    "timestamp": fix["timestamp"].isoformat(),
                    "changes_count": len(fix["suggestion"].code_changes),
                }
                for fix in self.applied_fixes
            ],
            "failed_fixes": [
                {"title": fix["suggestion"].title, "timestamp": fix["timestamp"].isoformat(), "error": fix["error"]}
                for fix in self.failed_fixes
            ],
        }

    def apply_pattern_based_fixes(
        self,
        pattern_matches: list[PatternMatch],
        fix_templates: dict[str, FixTemplate],
        auto_approve: bool = False,
    ) -> dict[str, Any]:
        """パターンベースの修正提案を適用

        Args:
            pattern_matches: パターンマッチ結果のリスト
            fix_templates: 修正テンプレート辞書（パターンID -> テンプレート）
            auto_approve: 自動承認フラグ

        Returns:
            適用結果の辞書

        """
        logger.info("パターンベースの修正適用を開始 (パターン数: %d)", len(pattern_matches))

        results = {
            "total_patterns": len(pattern_matches),
            "applied_count": 0,
            "skipped_count": 0,
            "failed_count": 0,
            "applied_fixes": [],
            "failed_fixes": [],
            "backups_created": [],
        }

        for i, pattern_match in enumerate(pattern_matches, 1):
            pattern_id = pattern_match.pattern.id

            # 対応する修正テンプレートを取得
            if pattern_id not in fix_templates:
                logger.warning("パターンに対応する修正テンプレートが見つかりません: %s", pattern_id)
                results["skipped_count"] += 1
                continue

            fix_template = fix_templates[pattern_id]

            logger.info(
                "パターンベース修正 %d/%d を処理中: %s (信頼度: %.2f)",
                i,
                len(pattern_matches),
                pattern_match.pattern.name,
                pattern_match.confidence,
            )

            try:
                # 修正テンプレートをFixSuggestionに変換
                fix_suggestion = self._convert_template_to_suggestion(fix_template, pattern_match)

                # 承認を確認
                if not auto_approve and self.interactive:
                    approval = self._request_pattern_approval(pattern_match, fix_template)
                    if not approval.approved:
                        logger.info("パターンベース修正をスキップ: %s", approval.reason)
                        results["skipped_count"] += 1
                        continue

                # 修正を適用
                apply_result = self._apply_single_fix(fix_suggestion)

                if apply_result["success"]:
                    results["applied_count"] += 1
                    results["applied_fixes"].append(apply_result)
                    results["backups_created"].extend(apply_result.get("backups", []))
                    logger.info("パターンベース修正を適用しました: %s", fix_template.name)
                else:
                    results["failed_count"] += 1
                    results["failed_fixes"].append(apply_result)
                    logger.error("パターンベース修正の適用に失敗: %s", apply_result.get("error", "不明なエラー"))

            except Exception as e:
                logger.error("パターンベース修正の処理中にエラー: %s", e)
                results["failed_count"] += 1
                results["failed_fixes"].append(
                    {
                        "pattern": pattern_match.pattern.name,
                        "template": fix_template.name,
                        "error": str(e),
                        "success": False,
                    },
                )

        logger.info(
            "パターンベース修正適用完了 - 適用: %d, スキップ: %d, 失敗: %d",
            results["applied_count"],
            results["skipped_count"],
            results["failed_count"],
        )

        return results

    def _convert_template_to_suggestion(self, fix_template: FixTemplate, pattern_match: PatternMatch) -> FixSuggestion:
        """修正テンプレートをFixSuggestionに変換

        Args:
            fix_template: 修正テンプレート
            pattern_match: パターンマッチ結果

        Returns:
            修正提案

        """
        # FixStepをCodeChangeに変換
        code_changes = []
        for step in fix_template.fix_steps:
            if step.type == "file_modification" and step.file_path:
                code_change = CodeChange(
                    file_path=step.file_path,
                    line_start=1,  # テンプレートベースの場合は全体を置換
                    line_end=1,
                    old_code="",  # 既存コードは自動検出
                    new_code=step.content or "",
                    description=step.description,
                )
                code_changes.append(code_change)

        # 信頼度を計算（パターンマッチの信頼度とテンプレートの成功率を組み合わせ）
        confidence = pattern_match.confidence * fix_template.success_rate

        return FixSuggestion(
            title=fix_template.name,
            description=fix_template.description,
            code_changes=code_changes,
            confidence=confidence,
            estimated_effort=fix_template.estimated_time,
        )

    def _request_pattern_approval(self, pattern_match: PatternMatch, fix_template: FixTemplate) -> FixApprovalResult:
        """パターンベース修正の承認を要求

        Args:
            pattern_match: パターンマッチ結果
            fix_template: 修正テンプレート

        Returns:
            承認結果

        """
        console.print(f"\n[cyan]🔍 検出されたパターン:[/cyan] {pattern_match.pattern.name}")
        console.print(f"[yellow]📊 信頼度:[/yellow] {pattern_match.confidence:.1%}")
        console.print(f"[green]🔧 提案される修正:[/green] {fix_template.name}")
        console.print(f"[red]⚠️  リスクレベル:[/red] {fix_template.risk_level}")
        console.print(f"[blue]⏱️  推定時間:[/blue] {fix_template.estimated_time}")
        console.print(f"[white]📝 説明:[/white] {fix_template.description}")

        if fix_template.fix_steps:
            console.print("\n[bold]📋 修正ステップ:[/bold]")
            for i, step in enumerate(fix_template.fix_steps, 1):
                console.print(f"  {i}. {step.description}")
                if step.file_path:
                    console.print(f"     [dim]ファイル: {step.file_path}[/dim]")

        while True:
            try:
                response = (
                    input("\nこのパターンベース修正を適用しますか? [y/n/s/q] (y=はい, n=いいえ, s=スキップ, q=終了): ")
                    .lower()
                    .strip()
                )

                if response in ["y", "yes"]:
                    return FixApprovalResult(True, "ユーザーが承認")
                if response in ["n", "no"]:
                    return FixApprovalResult(False, "ユーザーが拒否")
                if response in ["s", "skip"]:
                    return FixApprovalResult(False, "ユーザーがスキップ")
                if response in ["q", "quit"]:
                    raise KeyboardInterrupt("ユーザーが終了を選択")
                console.print("[red]無効な入力です。y, n, s, q のいずれかを入力してください。[/red]")

            except KeyboardInterrupt:
                return FixApprovalResult(False, "ユーザーが中断")
            except EOFError:
                return FixApprovalResult(False, "入力エラー")

    def cleanup_old_backups(self, keep_count: int = 20) -> None:
        """古いバックアップをクリーンアップ

        Args:
            keep_count: 保持するバックアップ数

        """
        self.backup_manager.cleanup_old_backups(keep_count)
