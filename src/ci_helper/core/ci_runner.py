"""
CI実行エンジン

actコマンドを使用してGitHub Actionsワークフローをローカルで実行します。
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

from ..core.exceptions import ExecutionError, SecurityError
from ..core.models import ExecutionResult, JobResult, StepResult, WorkflowResult
from ..core.security import EnvironmentSecretManager, SecurityValidator
from ..utils.config import Config


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
        # actコマンドの構築
        cmd = ["act"]

        # ワークフローファイルを指定
        cmd.extend(["-W", str(workflow_file)])

        # 設定からDockerイメージを取得
        act_image = self.config.get("act_image")
        if act_image:
            cmd.extend(["-P", f"ubuntu-latest={act_image}"])

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

    def validate_security(self, required_secrets: list[str] | None = None) -> dict[str, Any]:
        """セキュリティ設定を検証

        Args:
            required_secrets: 必須のシークレットキーリスト

        Returns:
            セキュリティ検証結果
        """
        return self.secret_manager.validate_secrets(required_secrets)

    def get_secret_summary(self) -> dict[str, Any]:
        """現在のシークレット設定状況を取得

        Returns:
            シークレット設定状況の辞書
        """
        return self.secret_manager.get_secret_summary()
