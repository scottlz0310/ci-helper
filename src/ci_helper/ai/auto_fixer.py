"""自動修正エンジン

パターンベースの修正提案を自動適用し、バックアップとロールバック機能を提供します。
"""

from __future__ import annotations

import hashlib
import logging
import shutil
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from ..utils.config import Config
from .approval_system import ApprovalDecision, UserApprovalSystem
from .exceptions import FixApplicationError
from .models import BackupFile, BackupInfo, FixResult, FixStep, FixSuggestion, FixTemplate, PatternMatch

logger = logging.getLogger(__name__)


class AutoFixer:
    """自動修正エンジン

    パターンベースの修正提案を安全に自動適用し、
    バックアップとロールバック機能を提供します。
    """

    def __init__(self, config: Config, interactive: bool = True, auto_approve_low_risk: bool = False):
        """自動修正エンジンを初期化

        Args:
            config: 設定オブジェクト
            interactive: 対話モード
            auto_approve_low_risk: 低リスク修正の自動承認

        """
        self.config = config
        self.project_root = Path.cwd()

        # バックアップディレクトリを設定
        self.backup_dir = config.get_path("cache_dir") / "auto_fix_backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # 承認システムを初期化
        self.approval_system = UserApprovalSystem(interactive=interactive, auto_approve_low_risk=auto_approve_low_risk)

        # 適用履歴を記録
        self.fix_history: list[dict[str, Any]] = []

    async def apply_fix(
        self,
        fix_suggestion: FixSuggestion,
        auto_approve: bool = False,
        approval_callback: Callable | None = None,
    ) -> FixResult:
        """修正提案を適用

        Args:
            fix_suggestion: 修正提案
            auto_approve: 自動承認フラグ
            approval_callback: 承認コールバック関数

        Returns:
            修正結果

        """
        logger.info("修正提案の適用を開始: %s", fix_suggestion.title)

        try:
            # 承認システムを使用した承認チェック
            if not auto_approve:
                approval_result = await self.approval_system.request_approval(fix_suggestion)

                if approval_result.decision == ApprovalDecision.REJECTED:
                    return FixResult(
                        success=False,
                        applied_steps=[],
                        error_message=f"修正が拒否されました: {approval_result.reason}",
                    )
                if approval_result.decision == ApprovalDecision.SKIPPED:
                    return FixResult(
                        success=False,
                        applied_steps=[],
                        error_message=f"修正がスキップされました: {approval_result.reason}",
                    )
                if approval_result.decision == ApprovalDecision.QUIT:
                    raise FixApplicationError(f"修正プロセスが中断されました: {approval_result.reason}")

            # バックアップを作成
            backup_info = self.create_backup(fix_suggestion)

            # 修正ステップを適用
            applied_steps: list[FixStep] = []
            for step in fix_suggestion.code_changes:
                # FixSuggestionのcode_changesをFixStepに変換
                fix_step = self._convert_code_change_to_fix_step(step)

                try:
                    self._apply_fix_step(fix_step)
                    applied_steps.append(fix_step)
                except Exception as e:
                    # 失敗時はロールバック
                    logger.error("修正ステップの適用に失敗: %s", e)
                    if backup_info:
                        self.rollback_changes(backup_info)

                    return FixResult(
                        success=False,
                        applied_steps=applied_steps,
                        backup_info=backup_info,
                        error_message=f"修正ステップの適用に失敗: {e}",
                        rollback_available=True,
                    )

            # 修正後の検証
            verification_result = self.verify_fix_application(fix_suggestion)
            verification_passed = verification_result["success"]

            # 結果を記録
            result = FixResult(
                success=True,
                applied_steps=applied_steps,
                backup_info=backup_info,
                verification_passed=verification_passed,
                rollback_available=backup_info is not None,
            )

            self._record_fix_history(fix_suggestion, result)

            logger.info("修正提案の適用が完了: %s", fix_suggestion.title)
            return result

        except Exception as e:
            logger.error("修正適用中にエラーが発生: %s", e)
            raise FixApplicationError(f"修正適用に失敗: {e}") from e

    def create_backup(self, fix_suggestion: FixSuggestion) -> BackupInfo | None:
        """修正前のバックアップを作成

        Args:
            fix_suggestion: 修正提案

        Returns:
            バックアップ情報（バックアップが不要な場合はNone）

        """
        # 変更対象ファイルを特定
        files_to_backup: set[str] = set()
        for change in fix_suggestion.code_changes:
            if change.file_path:
                files_to_backup.add(change.file_path)

        if not files_to_backup:
            logger.info("バックアップ対象ファイルがありません")
            return None

        # バックアップIDを生成
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_id = f"fix_{timestamp}_{hashlib.sha256(fix_suggestion.title.encode()).hexdigest()[:8]}"

        backup_files: list[BackupFile] = []
        nonexistent_files: list[BackupFile] = []

        for file_path in files_to_backup:
            # ファイルパスを正規化（絶対パスと相対パスの両方に対応）
            if Path(file_path).is_absolute():
                full_path = Path(file_path)
                # 絶対パスの場合、バックアップ用の相対パス名を生成
                backup_relative_path = Path(file_path).name
                # original_pathは絶対パス形式で保存（復元時に正確な場所に戻すため）
                original_path_for_backup = str(full_path)
            else:
                full_path = self.project_root / file_path
                backup_relative_path = file_path
                # original_pathは相対パス形式で保存
                original_path_for_backup = file_path

            if not full_path.exists():
                logger.warning("バックアップ対象ファイルが存在しません: %s", file_path)
                # 存在しないファイルを記録（後でロールバック時に削除するため）
                nonexistent_files.append(
                    BackupFile(
                        original_path=original_path_for_backup,
                        backup_path="",  # 空のパス（ファイルが存在しなかったことを示す）
                        checksum="",  # 空のチェックサム
                    ),
                )
                continue

            # バックアップファイルパスを生成
            backup_file_path = self.backup_dir / backup_id / backup_relative_path
            backup_file_path.parent.mkdir(parents=True, exist_ok=True)

            try:
                # ファイルをコピー
                shutil.copy2(full_path, backup_file_path)

                # チェックサムを計算
                checksum = self._calculate_checksum(full_path)

                backup_files.append(
                    BackupFile(
                        original_path=original_path_for_backup,
                        backup_path=str(backup_file_path),
                        checksum=checksum,
                    ),
                )

                logger.debug("ファイルをバックアップ: %s -> %s", file_path, backup_file_path)

            except Exception as e:
                logger.error("ファイルのバックアップに失敗: %s - %s", file_path, e)
                raise FixApplicationError(f"バックアップ作成に失敗: {e}") from e

        # 存在するファイルのバックアップがない場合でも、存在しないファイルの情報は保持する
        if not backup_files and not nonexistent_files:
            logger.info("バックアップ対象ファイルがありません")
            return None

        # 存在しないファイルのみの場合は空のファイルリストでバックアップ情報を作成
        if not backup_files and nonexistent_files:
            logger.info("バックアップ対象の既存ファイルがありません（存在しないファイルのみ）")
            backup_info = BackupInfo(
                backup_id=backup_id,
                created_at=datetime.now(),
                files=[],  # 空のファイルリスト
                description=f"修正提案適用前のバックアップ: {fix_suggestion.title}",
            )
            logger.info("バックアップを作成: %s (0 ファイル)", backup_id)
            return backup_info

        # 存在するファイルと存在しないファイルの情報を含めてバックアップ情報を作成
        all_backup_files = backup_files + nonexistent_files

        backup_info = BackupInfo(
            backup_id=backup_id,
            created_at=datetime.now(),
            files=all_backup_files,
            description=f"修正提案適用前のバックアップ: {fix_suggestion.title}",
        )

        logger.info("バックアップを作成: %s (%d ファイル)", backup_id, len(all_backup_files))
        return backup_info

    def rollback_changes(self, backup_info: BackupInfo) -> bool:
        """バックアップから変更をロールバック

        Args:
            backup_info: バックアップ情報

        Returns:
            ロールバック成功フラグ

        """
        logger.info("ロールバックを開始: %s", backup_info.backup_id)

        success_count = 0
        total_count = len(backup_info.files)

        for backup_file in backup_info.files:
            try:
                # original_pathが絶対パスか相対パスかを判定
                original_path_obj = Path(backup_file.original_path)
                if original_path_obj.is_absolute():
                    original_path = original_path_obj
                else:
                    original_path = self.project_root / backup_file.original_path

                # backup_pathが空の場合、元々ファイルが存在しなかったことを意味する
                if not backup_file.backup_path:
                    # 新規作成されたファイルを削除
                    if original_path.exists():
                        original_path.unlink()
                        logger.debug("新規作成ファイルを削除: %s", backup_file.original_path)
                    success_count += 1
                    continue

                backup_path = Path(backup_file.backup_path)

                if not backup_path.exists():
                    logger.error("バックアップファイルが存在しません: %s", backup_path)
                    continue

                # ディレクトリを作成（必要に応じて）
                original_path.parent.mkdir(parents=True, exist_ok=True)

                # ファイルを復元
                shutil.copy2(backup_path, original_path)

                # チェックサムを検証（空でない場合のみ）
                if backup_file.checksum:
                    restored_checksum = self._calculate_checksum(original_path)
                    if restored_checksum != backup_file.checksum:
                        logger.warning(
                            "復元後のチェックサムが一致しません: %s (期待: %s, 実際: %s)",
                            backup_file.original_path,
                            backup_file.checksum,
                            restored_checksum,
                        )

                success_count += 1
                logger.debug("ファイルを復元: %s", backup_file.original_path)

            except Exception as e:
                logger.error("ファイルの復元に失敗: %s - %s", backup_file.original_path, e)

        success = success_count == total_count

        if success:
            logger.info("ロールバックが完了: %s", backup_info.backup_id)
        else:
            logger.error(
                "ロールバックが部分的に失敗: %s (%d/%d ファイル成功)",
                backup_info.backup_id,
                success_count,
                total_count,
            )

        return success

    def verify_fix_application(self, fix_suggestion: FixSuggestion) -> dict[str, Any]:
        """修正適用後の検証を実行

        Args:
            fix_suggestion: 修正提案

        Returns:
            検証結果の詳細辞書

        """
        logger.info("修正適用後の検証を開始: %s", fix_suggestion.title)

        verification_result: dict[str, Any] = {
            "success": True,
            "checks_passed": [],
            "checks_failed": [],
            "warnings": [],
            "total_checks": 0,
            "passed_checks": 0,
        }

        try:
            # 基本的な検証: ファイルの存在と読み込み可能性
            for change in fix_suggestion.code_changes:
                if not change.file_path:
                    continue

                file_path = self.project_root / change.file_path
                verification_result["total_checks"] += 1

                # ファイルの存在確認
                if not file_path.exists():
                    error_msg = f"修正後にファイルが存在しません: {change.file_path}"
                    logger.error(error_msg)
                    verification_result["checks_failed"].append(error_msg)
                    verification_result["success"] = False
                    continue

                verification_result["checks_passed"].append(f"ファイル存在確認 OK: {change.file_path}")
                verification_result["passed_checks"] += 1

                # ファイルの読み込み確認
                try:
                    content = file_path.read_text(encoding="utf-8")
                    verification_result["checks_passed"].append(f"ファイル読み込み OK: {change.file_path}")
                    verification_result["passed_checks"] += 1
                    verification_result["total_checks"] += 1
                except Exception as e:
                    error_msg = f"修正後のファイルが読み込めません: {change.file_path} - {e}"
                    logger.error(error_msg)
                    verification_result["checks_failed"].append(error_msg)
                    verification_result["success"] = False
                    continue

                # ファイル形式別の詳細検証
                verification_result["total_checks"] += 1
                format_check = self._verify_file_format(file_path, content)
                if format_check["success"]:
                    verification_result["checks_passed"].append(format_check["message"])
                    verification_result["passed_checks"] += 1
                else:
                    verification_result["checks_failed"].append(format_check["message"])
                    verification_result["success"] = False

                # 警告レベルのチェック
                warnings = self._check_file_warnings(file_path, content)
                verification_result["warnings"].extend(warnings)

            # 全体的な整合性チェック
            integrity_checks = self._verify_project_integrity()
            verification_result["total_checks"] += len(integrity_checks)
            for check in integrity_checks:
                if check["success"]:
                    verification_result["checks_passed"].append(check["message"])
                    verification_result["passed_checks"] += 1
                else:
                    verification_result["checks_failed"].append(check["message"])
                    verification_result["success"] = False

            if verification_result["success"]:
                logger.info("修正適用後の検証が完了: %s", fix_suggestion.title)
            else:
                logger.error(
                    "修正適用後の検証に失敗: %s (%d/%d チェック通過)",
                    fix_suggestion.title,
                    verification_result["passed_checks"],
                    verification_result["total_checks"],
                )

            return verification_result

        except Exception as e:
            error_msg = f"検証中にエラーが発生: {e}"
            logger.error(error_msg)
            verification_result["success"] = False
            verification_result["checks_failed"].append(error_msg)
            return verification_result

    def _requires_approval(self, fix_suggestion: FixSuggestion) -> bool:
        """修正提案が承認を必要とするかチェック

        Args:
            fix_suggestion: 修正提案

        Returns:
            承認が必要かどうか

        """
        # 信頼度が低い場合は承認が必要
        if fix_suggestion.confidence < 0.8:
            return True

        # 重要なファイルを変更する場合は承認が必要
        important_files = {
            "pyproject.toml",
            "setup.py",
            "requirements.txt",
            "Dockerfile",
            "docker-compose.yml",
            ".github/workflows",
            ".actrc",
        }

        for change in fix_suggestion.code_changes:
            if change.file_path:
                file_path = Path(change.file_path)
                if any(str(file_path).startswith(important) for important in important_files):
                    return True

        return False

    def _convert_code_change_to_fix_step(self, code_change) -> FixStep:
        """CodeChangeをFixStepに変換

        Args:
            code_change: コード変更

        Returns:
            修正ステップ

        """
        return FixStep(
            type="file_modification",
            description=code_change.description,
            file_path=code_change.file_path,
            action="replace",
            content=code_change.new_code,
        )

    def _apply_fix_step(self, fix_step: FixStep) -> None:
        """修正ステップを適用

        Args:
            fix_step: 修正ステップ

        """
        if fix_step.type == "file_modification":
            self._apply_file_modification(fix_step)
        elif fix_step.type == "command":
            self._apply_command(fix_step)
        elif fix_step.type == "config_change":
            self._apply_config_change(fix_step)
        else:
            raise FixApplicationError(f"未対応の修正ステップタイプ: {fix_step.type}")

    def _apply_file_modification(self, fix_step: FixStep) -> None:
        """ファイル変更を適用

        Args:
            fix_step: 修正ステップ

        """
        if not fix_step.file_path:
            raise FixApplicationError("ファイルパスが指定されていません")

        # 絶対パスと相対パスの両方に対応
        if Path(fix_step.file_path).is_absolute():
            file_path = Path(fix_step.file_path)
        else:
            file_path = self.project_root / fix_step.file_path

        if fix_step.action == "create":
            # ファイル作成
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(fix_step.content or "", encoding="utf-8")

        elif fix_step.action == "append":
            # ファイル追記
            if file_path.exists():
                existing_content = file_path.read_text(encoding="utf-8")
                new_content = existing_content + (fix_step.content or "")
            else:
                new_content = fix_step.content or ""

            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(new_content, encoding="utf-8")

        elif fix_step.action == "replace":
            # ファイル置換
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(fix_step.content or "", encoding="utf-8")

        else:
            raise FixApplicationError(f"未対応のファイル操作: {fix_step.action}")

    def _apply_command(self, fix_step: FixStep) -> None:
        """コマンド実行を適用

        Args:
            fix_step: 修正ステップ

        """
        # セキュリティ上の理由で、現在はコマンド実行を無効化
        logger.warning("コマンド実行は現在サポートされていません: %s", fix_step.command)
        raise FixApplicationError("コマンド実行は現在サポートされていません")

    def _apply_config_change(self, fix_step: FixStep) -> None:
        """設定変更を適用

        Args:
            fix_step: 修正ステップ

        """
        # 設定ファイルの変更として処理
        self._apply_file_modification(fix_step)

    def _calculate_checksum(self, file_path: Path) -> str:
        """ファイルのチェックサムを計算

        Args:
            file_path: ファイルパス

        Returns:
            SHA256チェックサム

        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()

    def _check_python_syntax(self, file_path: Path) -> bool:
        """Python ファイルの構文チェック

        Args:
            file_path: ファイルパス

        Returns:
            構文が正しいかどうか

        """
        try:
            content = file_path.read_text(encoding="utf-8")
            compile(content, str(file_path), "exec")
            return True
        except SyntaxError as e:
            logger.error("Python 構文エラー: %s - 行 %d: %s", file_path, e.lineno, e.msg)
            return False
        except Exception as e:
            logger.error("Python 構文チェック失敗: %s - %s", file_path, e)
            return False

    def _record_fix_history(self, fix_suggestion: FixSuggestion, result: FixResult) -> None:
        """修正履歴を記録

        Args:
            fix_suggestion: 修正提案
            result: 修正結果

        """
        history_entry = {
            "timestamp": datetime.now(),
            "suggestion_title": fix_suggestion.title,
            "suggestion_confidence": fix_suggestion.confidence,
            "success": result.success,
            "applied_steps_count": len(result.applied_steps),
            "verification_passed": result.verification_passed,
            "backup_id": result.backup_info.backup_id if result.backup_info else None,
            "error_message": result.error_message,
        }

        self.fix_history.append(history_entry)
        logger.debug("修正履歴を記録: %s", history_entry)

    def get_fix_history(self) -> list[dict[str, Any]]:
        """修正履歴を取得

        Returns:
            修正履歴のリスト

        """
        return self.fix_history.copy()

    def cleanup_old_backups(self, keep_days: int = 30) -> None:
        """古いバックアップを削除

        Args:
            keep_days: 保持日数

        """
        cutoff_time = datetime.now().timestamp() - (keep_days * 24 * 60 * 60)

        deleted_count = 0
        for backup_dir in self.backup_dir.iterdir():
            if backup_dir.is_dir():
                try:
                    if backup_dir.stat().st_mtime < cutoff_time:
                        shutil.rmtree(backup_dir)
                        deleted_count += 1
                        logger.debug("古いバックアップを削除: %s", backup_dir)
                except Exception as e:
                    logger.warning("バックアップ削除に失敗: %s - %s", backup_dir, e)

        if deleted_count > 0:
            logger.info("古いバックアップを削除しました: %d 個", deleted_count)

    def _verify_file_format(self, file_path: Path, content: str) -> dict[str, Any]:
        """ファイル形式別の詳細検証

        Args:
            file_path: ファイルパス
            content: ファイル内容

        Returns:
            検証結果

        """
        result = {"success": True, "message": ""}

        try:
            if file_path.suffix == ".py":
                # Python ファイルの構文チェック
                if self._check_python_syntax(file_path):
                    result["message"] = f"Python 構文チェック OK: {file_path.name}"
                else:
                    result["success"] = False
                    result["message"] = f"Python 構文エラー: {file_path.name}"

            elif file_path.suffix == ".json":
                # JSON ファイルの構文チェック
                import json

                try:
                    json.loads(content)
                    result["message"] = f"JSON 構文チェック OK: {file_path.name}"
                except json.JSONDecodeError as e:
                    result["success"] = False
                    result["message"] = f"JSON 構文エラー: {file_path.name} - {e}"

            elif file_path.suffix in [".yml", ".yaml"]:
                # YAML ファイルの構文チェック
                try:
                    import yaml

                    yaml.safe_load(content)
                    result["message"] = f"YAML 構文チェック OK: {file_path.name}"
                except yaml.YAMLError as e:
                    result["success"] = False
                    result["message"] = f"YAML 構文エラー: {file_path.name} - {e}"
                except ImportError:
                    result["message"] = f"YAML チェックスキップ (PyYAML未インストール): {file_path.name}"

            elif file_path.suffix == ".toml":
                # TOML ファイルの構文チェック
                try:
                    import tomllib

                    tomllib.loads(content)
                    result["message"] = f"TOML 構文チェック OK: {file_path.name}"
                except tomllib.TOMLDecodeError as e:
                    result["success"] = False
                    result["message"] = f"TOML 構文エラー: {file_path.name} - {e}"

            else:
                # その他のファイルは基本的な文字エンコーディングチェックのみ
                result["message"] = f"ファイル形式チェック OK: {file_path.name}"

        except Exception as e:
            result["success"] = False
            result["message"] = f"ファイル形式チェック失敗: {file_path.name} - {e}"

        return result

    def _check_file_warnings(self, file_path: Path, content: str) -> list[str]:
        """ファイルの警告レベルチェック

        Args:
            file_path: ファイルパス
            content: ファイル内容

        Returns:
            警告メッセージのリスト

        """
        warnings = []

        try:
            # 大きすぎるファイルの警告
            if len(content) > 1024 * 1024:  # 1MB
                warnings.append(f"大きなファイル (>1MB): {file_path.name}")

            # 空ファイルの警告
            if not content.strip():
                warnings.append(f"空ファイル: {file_path.name}")

            # Python ファイル特有の警告
            if file_path.suffix == ".py":
                lines = content.splitlines()

                # 長すぎる行の警告
                long_lines = [i + 1 for i, line in enumerate(lines) if len(line) > 120]
                if long_lines:
                    warnings.append(f"長い行 (>120文字) が {len(long_lines)} 行: {file_path.name}")

                # TODO/FIXME コメントの警告
                todo_lines = [i + 1 for i, line in enumerate(lines) if "TODO" in line or "FIXME" in line]
                if todo_lines:
                    warnings.append(f"TODO/FIXME コメント: {file_path.name} (行: {todo_lines[:3]})")

            # 設定ファイルの警告
            if file_path.name in [".actrc", "pyproject.toml", "requirements.txt"]:
                if "password" in content.lower() or "secret" in content.lower():
                    warnings.append(f"機密情報の可能性: {file_path.name}")

        except Exception as e:
            warnings.append(f"警告チェック失敗: {file_path.name} - {e}")

        return warnings

    def _verify_project_integrity(self) -> list[dict[str, Any]]:
        """プロジェクト全体の整合性チェック

        Returns:
            整合性チェック結果のリスト

        """
        checks = []

        try:
            # 重要ファイルの存在チェック
            important_files = ["pyproject.toml", "README.md"]
            for file_name in important_files:
                file_path = self.project_root / file_name
                if file_path.exists():
                    checks.append({"success": True, "message": f"重要ファイル存在確認 OK: {file_name}"})
                else:
                    checks.append({"success": False, "message": f"重要ファイルが見つかりません: {file_name}"})

            # Git リポジトリの整合性チェック
            git_dir = self.project_root / ".git"
            if git_dir.exists():
                checks.append({"success": True, "message": "Git リポジトリ整合性 OK"})
            else:
                checks.append({"success": False, "message": "Git リポジトリが見つかりません"})

            # Python プロジェクトの場合の追加チェック
            pyproject_path = self.project_root / "pyproject.toml"
            if pyproject_path.exists():
                try:
                    import tomllib

                    content = pyproject_path.read_text(encoding="utf-8")
                    config = tomllib.loads(content)

                    if "project" in config or "tool" in config:
                        checks.append({"success": True, "message": "Python プロジェクト設定 OK"})
                    else:
                        checks.append({"success": False, "message": "pyproject.toml の設定が不完全"})

                except Exception as e:
                    checks.append({"success": False, "message": f"pyproject.toml の検証に失敗: {e}"})

        except Exception as e:
            checks.append({"success": False, "message": f"プロジェクト整合性チェック失敗: {e}"})

        return checks

    def get_backup_list(self) -> list[dict[str, Any]]:
        """利用可能なバックアップのリストを取得

        Returns:
            バックアップ情報のリスト

        """
        backups = []

        try:
            for backup_dir in self.backup_dir.iterdir():
                if backup_dir.is_dir():
                    backup_info = {
                        "backup_id": backup_dir.name,
                        "created_at": datetime.fromtimestamp(backup_dir.stat().st_mtime),
                        "file_count": len(list(backup_dir.rglob("*"))),
                        "size_mb": sum(f.stat().st_size for f in backup_dir.rglob("*") if f.is_file()) / (1024 * 1024),
                    }
                    backups.append(backup_info)

            # 作成日時でソート（新しい順）
            backups.sort(key=lambda x: x["created_at"], reverse=True)

        except Exception as e:
            logger.error("バックアップリスト取得に失敗: %s", e)

        return backups

    def rollback_by_backup_id(self, backup_id: str) -> dict[str, Any]:
        """バックアップIDを指定してロールバック

        Args:
            backup_id: バックアップID

        Returns:
            ロールバック結果

        """
        backup_path = self.backup_dir / backup_id

        if not backup_path.exists():
            return {
                "success": False,
                "error": f"バックアップが見つかりません: {backup_id}",
                "restored_files": [],
                "failed_files": [],
            }

        result = {"success": True, "restored_files": [], "failed_files": [], "backup_id": backup_id}

        try:
            # バックアップディレクトリ内のすべてのファイルを復元
            for backup_file in backup_path.rglob("*"):
                if backup_file.is_file():
                    # 相対パスを計算
                    relative_path = backup_file.relative_to(backup_path)
                    original_path = self.project_root / relative_path

                    try:
                        # ディレクトリを作成
                        original_path.parent.mkdir(parents=True, exist_ok=True)

                        # ファイルを復元
                        shutil.copy2(backup_file, original_path)
                        result["restored_files"].append(str(relative_path))

                    except Exception as e:
                        error_info = {"file": str(relative_path), "error": str(e)}
                        result["failed_files"].append(error_info)
                        result["success"] = False

            if result["success"]:
                logger.info("バックアップからの復元が完了: %s", backup_id)
            else:
                logger.error(
                    "バックアップからの復元が部分的に失敗: %s (%d 成功, %d 失敗)",
                    backup_id,
                    len(result["restored_files"]),
                    len(result["failed_files"]),
                )

        except Exception as e:
            result["success"] = False
            result["error"] = str(e)
            logger.error("バックアップからの復元中にエラー: %s", e)

        return result

    async def apply_pattern_based_fix(
        self,
        fix_suggestion: FixSuggestion,
        pattern_match: PatternMatch | None = None,
        fix_template: FixTemplate | None = None,
        auto_approve: bool = False,
    ) -> FixResult:
        """パターンベースの修正提案を適用

        Args:
            fix_suggestion: 修正提案
            pattern_match: パターンマッチ結果
            fix_template: 修正テンプレート
            auto_approve: 自動承認フラグ

        Returns:
            修正結果

        """
        logger.info("パターンベース修正提案の適用を開始: %s", fix_suggestion.title)

        try:
            # パターン情報を含む承認チェック
            if not auto_approve:
                approval_result = await self.approval_system.request_approval(
                    fix_suggestion,
                    pattern_match,
                    fix_template,
                )

                if approval_result.decision == ApprovalDecision.REJECTED:
                    return FixResult(
                        success=False,
                        applied_steps=[],
                        error_message=f"パターンベース修正が拒否されました: {approval_result.reason}",
                    )
                if approval_result.decision == ApprovalDecision.SKIPPED:
                    return FixResult(
                        success=False,
                        applied_steps=[],
                        error_message=f"パターンベース修正がスキップされました: {approval_result.reason}",
                    )
                if approval_result.decision == ApprovalDecision.QUIT:
                    raise FixApplicationError(f"パターンベース修正プロセスが中断されました: {approval_result.reason}")

            # 通常の修正適用フローを実行
            return await self.apply_fix(fix_suggestion, auto_approve=True)

        except Exception as e:
            logger.error("パターンベース修正適用中にエラーが発生: %s", e)
            raise FixApplicationError(f"パターンベース修正適用に失敗: {e}") from e

    def get_approval_summary(self) -> dict[str, Any]:
        """承認システムのサマリーを取得

        Returns:
            承認サマリー

        """
        return self.approval_system.get_approval_summary()

    def set_approval_policy(self, auto_approve_low_risk: bool = False) -> None:
        """承認ポリシーを設定

        Args:
            auto_approve_low_risk: 低リスク修正の自動承認

        """
        self.approval_system.set_auto_approve_policy(low_risk=auto_approve_low_risk)
