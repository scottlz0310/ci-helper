"""
CI実行エンジン

actコマンドを使用してGitHub Actionsワークフローをローカルで実行します。
"""

from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

from ..core.exceptions import ExecutionError, SecurityError
from ..core.models import ExecutionResult, JobResult, StepResult, WorkflowResult
from ..core.security import EnvironmentSecretManager, SecretSummary, SecretValidationResult, SecurityValidator
from ..utils.config import Config

logger = logging.getLogger(__name__)


class CIRunner:
    """CI実行エンジン

    actコマンドを使用してワークフローを実行し、結果を管理します。
    """

    def __init__(self, config: Config):
        """CI実行エンジンを初期化

        Args:
            config: 設定オブジェクト
        """
        self.config = config
        self.project_root = config.project_root
        self.secret_manager = EnvironmentSecretManager()
        self.security_validator = SecurityValidator()

    def run_workflows(
        self,
        workflows: Sequence[str] | None = None,
        verbose: bool = False,
        dry_run: bool = False,
        save_logs: bool = True,
    ) -> ExecutionResult:
        """ワークフローを実行

        Args:
            workflows: 実行するワークフローファイル名のリスト（Noneの場合は全て）
            verbose: 詳細出力フラグ
            dry_run: ドライランフラグ（実際には実行しない）
            save_logs: ログ保存フラグ

        Returns:
            実行結果

        Raises:
            ExecutionError: 実行に失敗した場合
        """
        start_time = time.time()

        if not dry_run:
            self._check_lock_file()

        # ワークフローファイルを検出
        workflow_files = self._discover_workflows(workflows)
        if not workflow_files:
            raise ExecutionError(
                "実行するワークフローが見つかりません",
                ".github/workflows/ ディレクトリにワークフローファイルがあることを確認してください",
            )

        workflow_results = []
        overall_success = True
        all_output = []

        for workflow_file in workflow_files:
            if dry_run:
                # ドライランの場合は実行をスキップ
                workflow_result = WorkflowResult(
                    name=workflow_file.name,
                    success=True,
                    jobs=[],
                    duration=0.0,
                )
                all_output.append(f"[DRY RUN] Would execute: {workflow_file.name}")
            else:
                workflow_result, output = self._run_single_workflow(workflow_file, verbose)
                all_output.append(output)
                if not workflow_result.success:
                    overall_success = False

            workflow_results.append(workflow_result)

        total_duration = time.time() - start_time
        combined_output = "\n".join(all_output)

        execution_result = ExecutionResult(
            success=overall_success,
            workflows=workflow_results,
            total_duration=total_duration,
        )

        # ログ保存（save_logsがTrueかつドライランでない場合）
        if save_logs and not dry_run:
            from .log_manager import LogManager

            log_manager = LogManager(self.config)
            command_args = {
                "workflows": workflows,
                "verbose": verbose,
                "dry_run": dry_run,
            }
            log_manager.save_execution_log(execution_result, combined_output, command_args)

            # 実行履歴のメタデータも保存
            log_manager.save_execution_history_metadata(execution_result)

        return execution_result

    def _discover_workflows(self, workflow_names: Sequence[str] | None = None) -> list[Path]:
        """ワークフローファイルを検出

        Args:
            workflow_names: 指定されたワークフロー名（Noneの場合は全て検出）

        Returns:
            ワークフローファイルのパスリスト
        """
        workflows_dir = self.project_root / ".github" / "workflows"
        if not workflows_dir.exists():
            return []

        if workflow_names:
            # 指定されたワークフローのみ
            workflow_files = []
            for name in workflow_names:
                # .yml または .yaml 拡張子を試す
                for ext in [".yml", ".yaml"]:
                    workflow_path = workflows_dir / f"{name}{ext}"
                    if workflow_path.exists():
                        workflow_files.append(workflow_path)
                        break
                    # 拡張子が既に含まれている場合
                    workflow_path = workflows_dir / name
                    if workflow_path.exists():
                        workflow_files.append(workflow_path)
                        break
        else:
            # 全てのワークフローファイルを検出
            workflow_files = list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))

        return sorted(workflow_files)

    def _run_single_workflow(self, workflow_file: Path, verbose: bool = False) -> tuple[WorkflowResult, str]:
        """単一のワークフローを実行

        Args:
            workflow_file: ワークフローファイルのパス
            verbose: 詳細出力フラグ

        Returns:
            ワークフロー実行結果と出力のタプル
        """
        start_time = time.time()

        try:
            result = self._execute_act(workflow_file, verbose)
            success = result.returncode == 0
            duration = time.time() - start_time
            output = result.stdout + result.stderr

            # 基本的なジョブ結果を作成（詳細な解析は後のタスクで実装）
            job_result = JobResult(
                name="default",
                success=success,
                failures=[],
                steps=[
                    StepResult(
                        name="act execution",
                        success=success,
                        duration=duration,
                        output=output,
                    )
                ],
                duration=duration,
            )

            workflow_result = WorkflowResult(
                name=workflow_file.name,
                success=success,
                jobs=[job_result],
                duration=duration,
            )

            return workflow_result, output

        except subprocess.TimeoutExpired as e:
            duration = time.time() - start_time
            raise ExecutionError(
                f"ワークフロー '{workflow_file.name}' の実行がタイムアウトしました",
                f"タイムアウト時間: {self.config.get('timeout_seconds')}秒",
            ) from e

        except Exception as e:
            raise ExecutionError(
                f"ワークフロー '{workflow_file.name}' の実行に失敗しました",
                f"エラー詳細: {e}",
            ) from e

    def _execute_act(self, workflow_file: Path, verbose: bool = False) -> subprocess.CompletedProcess[str]:
        """actコマンドを実行

        Args:
            workflow_file: ワークフローファイルのパス
            verbose: 詳細出力フラグ

        Returns:
            subprocess実行結果

        Raises:
            ExecutionError: actコマンドの実行に失敗した場合
        """
        # 実行前のファイル所有権を記録
        original_ownership = self._record_file_ownership()

        # actコマンドの構築
        cmd = ["act"]

        # ワークフローファイルを指定
        cmd.extend(["-W", str(workflow_file)])

        # 設定からDockerイメージを取得
        act_image = self.config.get("act_image")
        if act_image:
            cmd.extend(["-P", f"ubuntu-latest={act_image}"])

        # ファイル所有権保持のためのオプションを追加
        self._add_ownership_preservation_options(cmd)

        # 詳細出力
        if verbose:
            cmd.append("-v")

        # 環境変数ファイルの指定（シークレット管理）
        env_file = self.config.get("env_file")
        if env_file and Path(env_file).exists():
            cmd.extend(["--env-file", env_file])

        # .actrcファイルがある場合は自動的に読み込まれる

        # 安全な環境変数を準備
        safe_env = self._prepare_secure_environment()

        try:
            # actコマンドを実行
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=self.config.get("timeout_seconds", 1800),
                check=False,  # エラーでも例外を発生させない
                env=safe_env,  # 安全な環境変数を使用
            )

            # 実行後にファイル所有権をチェックして修正
            self._restore_file_ownership(original_ownership)

            return result

        except FileNotFoundError as e:
            raise ExecutionError(
                "actコマンドが見つかりません",
                "actをインストールしてください: https://github.com/nektos/act#installation",
            ) from e

        except subprocess.TimeoutExpired as e:
            raise ExecutionError(
                f"actコマンドの実行がタイムアウトしました（{self.config.get('timeout_seconds')}秒）",
                "より長いタイムアウト時間を設定するか、ワークフローを最適化してください",
            ) from e

    def _record_file_ownership(self) -> dict[str, tuple[int, int]]:
        """実行前のファイル所有権を記録

        Returns:
            ファイルパスと(uid, gid)のマッピング
        """
        ownership_map = {}

        try:
            # プロジェクトルート配下の重要なファイル・ディレクトリの所有権を記録
            important_paths = [
                self.project_root,
                self.project_root / ".github",
                self.project_root / ".ci-helper",
            ]

            # 存在するパスのみを対象とする
            for path in important_paths:
                if path.exists():
                    stat_info = path.stat()
                    ownership_map[str(path)] = (stat_info.st_uid, stat_info.st_gid)

                    # ディレクトリの場合は中身も記録
                    if path.is_dir():
                        for item in path.rglob("*"):
                            if item.exists():
                                item_stat = item.stat()
                                ownership_map[str(item)] = (item_stat.st_uid, item_stat.st_gid)

        except (OSError, PermissionError) as e:
            logger.warning(f"ファイル所有権の記録に失敗しました: {e}")

        return ownership_map

    def _add_ownership_preservation_options(self, cmd: list[str]) -> None:
        """ファイル所有権保持のためのオプションを追加

        Args:
            cmd: actコマンドのリスト
        """
        import os

        # 現在のユーザーIDとグループIDを取得
        uid = os.getuid()
        gid = os.getgid()

        # Dockerコンテナ内でホストユーザーと同じUID/GIDを使用
        cmd.extend(["--container-options", f"--user {uid}:{gid}"])

        logger.debug(f"Docker実行時のユーザー設定: {uid}:{gid}")

    def _restore_file_ownership(self, original_ownership: dict[str, tuple[int, int]]) -> None:
        """ファイル所有権を元に戻す

        Args:
            original_ownership: 元の所有権情報
        """
        import os

        changed_files = []

        try:
            for file_path, (original_uid, original_gid) in original_ownership.items():
                path = Path(file_path)
                if not path.exists():
                    continue

                current_stat = path.stat()
                current_uid = current_stat.st_uid
                current_gid = current_stat.st_gid

                # 所有権が変更されている場合
                if current_uid != original_uid or current_gid != original_gid:
                    changed_files.append(str(path))

                    try:
                        # 所有権を復元
                        os.chown(path, original_uid, original_gid)
                        logger.debug(
                            f"所有権を復元しました: {path} ({current_uid}:{current_gid} -> {original_uid}:{original_gid})"
                        )
                    except (OSError, PermissionError) as e:
                        logger.warning(f"所有権の復元に失敗しました: {path} - {e}")

            if changed_files:
                logger.info(f"ファイル所有権を修正しました: {len(changed_files)}個のファイル")
                if logger.isEnabledFor(logging.DEBUG):
                    for file_path in changed_files[:10]:  # 最初の10個のみ表示
                        logger.debug(f"  修正: {file_path}")
                    if len(changed_files) > 10:
                        logger.debug(f"  ... 他{len(changed_files) - 10}個")

        except Exception as e:
            logger.error(f"ファイル所有権の復元処理でエラーが発生しました: {e}")
            # 手動修正のガイダンスを表示
            self._show_manual_fix_guidance()

    def _show_manual_fix_guidance(self) -> None:
        """手動でのファイル所有権修正ガイダンスを表示"""
        import os

        current_user = os.getenv("USER", "user")

        logger.error("ファイル所有権の自動修正に失敗しました。")
        logger.error("以下のコマンドで手動修正してください:")
        logger.error(f"  sudo chown -R {current_user}:{current_user} .")
        logger.error("または、現在のユーザー名が異なる場合:")
        logger.error("  sudo chown -R $(whoami):$(whoami) .")

    def _prepare_secure_environment(self) -> dict[str, str]:
        """act実行用の安全な環境変数を準備

        Returns:
            安全な環境変数の辞書

        Raises:
            SecurityError: セキュリティ検証に失敗した場合
        """
        try:
            # 追加の環境変数を設定から取得
            additional_vars = self.config.get("environment_variables", {})

            # 安全な環境変数を準備
            safe_env = self.secret_manager.prepare_act_environment(additional_vars)

            return safe_env

        except Exception as e:
            raise SecurityError(
                "環境変数の準備中にエラーが発生しました",
                "環境変数の設定を確認してください",
            ) from e

    def check_dependencies(self) -> dict[str, bool]:
        """依存関係をチェック

        Returns:
            依存関係のチェック結果
        """
        checks = {}

        # actコマンドの存在確認
        try:
            subprocess.run(["act", "--version"], capture_output=True, check=True, timeout=10)
            checks["act"] = True
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            checks["act"] = False

        # Dockerデーモンの確認
        try:
            subprocess.run(["docker", "info"], capture_output=True, check=True, timeout=10)
            checks["docker"] = True
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            checks["docker"] = False

        # .github/workflowsディレクトリの確認
        workflows_dir = self.project_root / ".github" / "workflows"
        checks["workflows_dir"] = workflows_dir.exists() and workflows_dir.is_dir()

        return checks

    def validate_security(self, required_secrets: list[str] | None = None) -> SecretValidationResult:
        """セキュリティ設定を検証

        Args:
            required_secrets: 必須のシークレットキーリスト

        Returns:
            セキュリティ検証結果
        """
        return self.secret_manager.validate_secrets(required_secrets)

    def get_secret_summary(self) -> SecretSummary:
        """現在のシークレット設定状況を取得

        Returns:
            シークレット設定状況の辞書
        """
        return self.secret_manager.get_secret_summary()

    def _check_lock_file(self) -> None:
        """ロックファイルをチェックして同時実行を防ぐ

        Raises:
            ExecutionError: 他のインスタンスが実行中の場合
        """
        lock_file = self.config.project_root / ".ci-helper" / "ci-helper.lock"
        if lock_file.exists():
            raise ExecutionError(
                "他のci-helperインスタンスが実行中です",
                "実行が完了するまでお待ちください",
            )
