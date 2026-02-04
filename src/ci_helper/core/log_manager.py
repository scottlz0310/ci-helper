"""ログ管理システム

CI実行ログの保存、管理、一覧表示機能を提供します。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from ..core.exceptions import ExecutionError
from ..core.models import ExecutionResult
from ..utils.config import Config


class LogManager:
    """ログ管理クラス

    実行ログの保存、メタデータ管理、一覧表示を行います。
    """

    def __init__(self, config: Config):
        """ログマネージャーを初期化

        Args:
            config: 設定オブジェクト

        """
        self.config = config
        self.log_dir = config.get_path("log_dir")
        self.index_file = self.log_dir / "index.json"

        # ログディレクトリを作成
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def save_execution_log(
        self,
        execution_result: ExecutionResult,
        raw_output: str,
        command_args: dict[str, Any] | None = None,
    ) -> Path:
        """実行ログを保存

        Args:
            execution_result: 実行結果
            raw_output: 生のact出力
            command_args: 実行時のコマンド引数

        Returns:
            保存されたログファイルのパス

        Raises:
            ExecutionError: ログ保存に失敗した場合

        """
        log_path: Path | None = None
        try:
            # タイムスタンプ付きのログファイル名を生成
            timestamp = execution_result.timestamp.strftime("%Y%m%d_%H%M%S")
            log_filename = f"act_{timestamp}.log"
            log_path = self.log_dir / log_filename

            # 生ログを保存
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(raw_output)

            # メタデータを更新
            self._update_log_index(log_path, execution_result, command_args)

            # ExecutionResultにログパスを設定
            execution_result.log_path = str(log_path)

            return log_path

        except Exception as e:
            path_str = str(log_path) if log_path else "unknown"
            raise ExecutionError(
                f"ログの保存に失敗しました: {path_str}",
                f"ディスク容量やファイル権限を確認してください: {e}",
            ) from e

    def _update_log_index(
        self,
        log_path: Path,
        execution_result: ExecutionResult,
        command_args: dict[str, Any] | None = None,
    ) -> None:
        """ログインデックスを更新

        Args:
            log_path: ログファイルのパス
            execution_result: 実行結果
            command_args: 実行時のコマンド引数

        """
        # 既存のインデックスを読み込み
        index_data: dict[str, Any] = self._load_log_index()

        # 新しいエントリを追加
        log_entry = {
            "timestamp": execution_result.timestamp.isoformat(),
            "log_file": log_path.name,
            "success": execution_result.success,
            "total_duration": execution_result.total_duration,
            "total_failures": execution_result.total_failures,
            "workflows": [
                {
                    "name": w.name,
                    "success": w.success,
                    "duration": w.duration,
                    "job_count": len(w.jobs),
                }
                for w in execution_result.workflows
            ],
            "command_args": command_args or {},
            "file_size": log_path.stat().st_size,
        }

        logs_value = index_data.setdefault("logs", [])
        if not isinstance(logs_value, list):
            logs_value = []
            index_data["logs"] = logs_value
        logs_list = cast("list[dict[str, Any]]", logs_value)
        logs_list.append(log_entry)

        # 最新の実行情報を更新
        index_data["last_execution"] = log_entry

        # インデックスファイルに保存
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(index_data, f, indent=2, ensure_ascii=False)

    def _load_log_index(self) -> dict[str, Any]:
        """ログインデックスを読み込み

        Returns:
            インデックスデータ

        """
        if not self.index_file.exists():
            return {
                "version": "1.0",
                "created": datetime.now().isoformat(),
                "logs": [],
                "last_execution": None,
            }

        try:
            with open(self.index_file, encoding="utf-8") as f:
                loaded = json.load(f)
                return cast("dict[str, Any]", loaded)
        except json.JSONDecodeError, OSError:
            # 破損したインデックスファイルの場合は新規作成
            return {
                "version": "1.0",
                "created": datetime.now().isoformat(),
                "logs": [],
                "last_execution": None,
            }

    def list_logs(self, limit: int | None = None) -> list[dict[str, Any]]:
        """ログ一覧を取得

        Args:
            limit: 取得する最大件数（Noneの場合は全て）

        Returns:
            ログエントリのリスト（新しい順）

        """
        index_data: dict[str, Any] = self._load_log_index()
        logs_value = index_data.get("logs", [])
        logs: list[dict[str, Any]] = []

        if isinstance(logs_value, list):
            logs = cast("list[dict[str, Any]]", logs_value)

        # インデックスにログがない場合はディレクトリを直接スキャン
        if not logs:
            logs = self._load_logs_from_directory()

        # タイムスタンプで降順ソート（新しい順）
        logs.sort(key=lambda x: x["timestamp"], reverse=True)

        if limit is not None:
            logs = logs[:limit]

        return logs

    def get_log_content(self, log_filename: str) -> str:
        """ログファイルの内容を取得

        Args:
            log_filename: ログファイル名

        Returns:
            ログファイルの内容

        Raises:
            ExecutionError: ログファイルが見つからない場合

        """
        log_path = self.log_dir / log_filename

        if not log_path.exists():
            raise ExecutionError(
                f"ログファイルが見つかりません: {log_filename}",
                f"利用可能なログ: {[log['log_file'] for log in self.list_logs()]}",
            )

        try:
            with open(log_path, encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            raise ExecutionError(
                f"ログファイルの読み込みに失敗しました: {log_filename}",
                f"ファイル権限を確認してください: {e}",
            ) from e

    def get_latest_log(self) -> dict[str, Any] | None:
        """最新のログエントリを取得

        Returns:
            最新のログエントリ（存在しない場合はNone）

        """
        index_data: dict[str, Any] = self._load_log_index()
        last_execution = index_data.get("last_execution")
        if isinstance(last_execution, dict):
            return cast("dict[str, Any]", last_execution)
        return None

    def _load_logs_from_directory(self) -> list[dict[str, Any]]:
        """ログディレクトリからインデックスなしでログを収集"""
        if not self.log_dir.exists():
            return []

        log_entries: list[dict[str, Any]] = []
        for log_path in self.log_dir.glob("*.log"):
            if not log_path.is_file():
                continue

            timestamp = self._extract_timestamp_from_filename(log_path)
            log_entries.append(
                {
                    "timestamp": timestamp,
                    "log_file": log_path.name,
                    "success": False,
                    "total_duration": 0.0,
                    "total_failures": 0,
                    "workflows": [],
                },
            )

        return log_entries

    def _extract_timestamp_from_filename(self, log_path: Path) -> str:
        """ログファイル名からタイムスタンプを抽出"""
        stem = log_path.stem
        if stem.startswith("act_"):
            raw_timestamp = stem[4:]
            for fmt in ("%Y%m%d_%H%M%S", "%Y%m%d%H%M%S"):
                try:
                    parsed = datetime.strptime(raw_timestamp, fmt)
                    return parsed.isoformat()
                except ValueError:
                    continue

        # ファイル名から取得できない場合は更新日時を使用
        return datetime.fromtimestamp(log_path.stat().st_mtime).isoformat()

    def cleanup_old_logs(self, max_count: int | None = None, max_size_mb: int | None = None) -> int:
        """古いログファイルをクリーンアップ

        Args:
            max_count: 保持する最大ログ数
            max_size_mb: 保持する最大サイズ（MB）

        Returns:
            削除されたファイル数

        """
        if max_count is None:
            max_count = 50  # デフォルトで50件まで保持

        if max_size_mb is None:
            max_size_mb = self.config.get("max_log_size_mb", 100)

        logs = self.list_logs()
        deleted_count = 0

        # 件数制限による削除
        if len(logs) > max_count:
            logs_to_delete = logs[max_count:]
            for log_entry in logs_to_delete:
                log_path = self.log_dir / log_entry["log_file"]
                if log_path.exists():
                    log_path.unlink()
                    deleted_count += 1

        # サイズ制限による削除
        total_size = 0
        remaining_logs: list[dict[str, Any]] = []

        for log_entry in logs[:max_count]:
            log_path = self.log_dir / log_entry["log_file"]
            if log_path.exists():
                file_size = log_path.stat().st_size
                if max_size_mb is not None and total_size + file_size > max_size_mb * 1024 * 1024:
                    # サイズ制限を超える場合は削除
                    log_path.unlink()
                    deleted_count += 1
                else:
                    total_size += file_size
                    remaining_logs.append(log_entry)
            else:
                # ファイルが存在しない場合はインデックスから除外
                deleted_count += 1

        # インデックスを更新
        if deleted_count > 0:
            index_data = self._load_log_index()
            index_data["logs"] = remaining_logs
            if remaining_logs:
                index_data["last_execution"] = remaining_logs[0]
            else:
                index_data["last_execution"] = None

            with open(self.index_file, "w", encoding="utf-8") as f:
                json.dump(index_data, f, indent=2, ensure_ascii=False)

        return deleted_count

    def get_log_statistics(self) -> dict[str, Any]:
        """ログ統計情報を取得

        Returns:
            ログ統計情報

        """
        logs = self.list_logs()

        if not logs:
            return {
                "total_logs": 0,
                "total_size_mb": 0,
                "success_rate": 0,
                "average_duration": 0,
            }

        total_size = sum(
            (self.log_dir / log["log_file"]).stat().st_size for log in logs if (self.log_dir / log["log_file"]).exists()
        )

        successful_logs = [log for log in logs if log["success"]]
        total_duration = sum(log["total_duration"] for log in logs)

        return {
            "total_logs": len(logs),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "success_rate": round(len(successful_logs) / len(logs) * 100, 1) if logs else 0,
            "average_duration": round(total_duration / len(logs), 2) if logs else 0,
            "latest_execution": logs[0]["timestamp"] if logs else None,
        }

    def find_logs_by_workflow(self, workflow_name: str) -> list[dict[str, Any]]:
        """特定のワークフローのログを検索

        Args:
            workflow_name: ワークフロー名

        Returns:
            該当するログエントリのリスト

        """
        logs = self.list_logs()
        matching_logs: list[dict[str, Any]] = []

        for log in logs:
            workflows = log.get("workflows", [])
            if any(w["name"] == workflow_name for w in workflows):
                matching_logs.append(log)

        return matching_logs

    def get_execution_history(self, limit: int | None = None) -> list[ExecutionResult]:
        """実行履歴をExecutionResultオブジェクトのリストとして取得

        Args:
            limit: 取得する最大件数（Noneの場合は全て）

        Returns:
            ExecutionResultオブジェクトのリスト（新しい順）

        """
        logs = self.list_logs(limit)
        execution_results: list[ExecutionResult] = []

        for log_entry in logs:
            try:
                # ログファイルから実行結果を復元
                execution_result = self._restore_execution_result(log_entry)
                if execution_result:
                    execution_results.append(execution_result)
            except Exception:
                # 復元に失敗した場合はスキップ
                continue

        return execution_results

    def _restore_execution_result(self, log_entry: dict[str, Any]) -> ExecutionResult | None:
        """ログエントリからExecutionResultを復元

        Args:
            log_entry: ログエントリ

        Returns:
            復元されたExecutionResult（失敗時はNone）

        """
        try:
            from datetime import datetime

            from ..core.log_analyzer import LogAnalyzer
            from ..core.models import WorkflowResult

            # ログファイルの内容を読み込み
            log_content = self.get_log_content(log_entry["log_file"])

            # ログアナライザーで解析
            log_analyzer = LogAnalyzer()
            execution_result = log_analyzer.analyze_log(log_content)

            # メタデータから情報を復元
            execution_result.success = log_entry["success"]
            execution_result.total_duration = log_entry["total_duration"]
            execution_result.log_path = str(self.log_dir / log_entry["log_file"])
            execution_result.timestamp = datetime.fromisoformat(log_entry["timestamp"])

            # ワークフロー情報を復元
            if "workflows" in log_entry:
                restored_workflows: list[WorkflowResult] = []
                for workflow_meta in log_entry["workflows"]:
                    # 既存のワークフローを検索
                    existing_workflow = None
                    for w in execution_result.workflows:
                        if w.name == workflow_meta["name"]:
                            existing_workflow = w
                            break

                    if existing_workflow:
                        # メタデータで更新
                        existing_workflow.success = workflow_meta["success"]
                        existing_workflow.duration = workflow_meta["duration"]
                        restored_workflows.append(existing_workflow)
                    else:
                        # 新しいワークフローを作成
                        workflow_result = WorkflowResult(
                            name=workflow_meta["name"],
                            success=workflow_meta["success"],
                            jobs=[],
                            duration=workflow_meta["duration"],
                        )
                        restored_workflows.append(workflow_result)

                execution_result.workflows = restored_workflows

            return execution_result

        except Exception:
            return None

    def get_previous_execution(self, current_timestamp: datetime | None = None) -> ExecutionResult | None:
        """前回の実行結果を取得

        Args:
            current_timestamp: 現在の実行のタイムスタンプ（指定時はそれより前の実行を取得）

        Returns:
            前回のExecutionResult（存在しない場合はNone）

        """
        execution_history = self.get_execution_history()

        if not execution_history:
            return None

        # 現在のタイムスタンプが指定されている場合は、それより前の実行を検索
        if current_timestamp:
            for execution in execution_history:
                if execution.timestamp < current_timestamp:
                    return execution
            return None
        # 最新の実行を返す
        return execution_history[0] if execution_history else None

    def save_execution_history_metadata(self, execution_result: ExecutionResult) -> None:
        """実行履歴のメタデータを保存

        Args:
            execution_result: 実行結果

        """
        # 既存のインデックスを更新（save_execution_logで既に行われているが、追加情報を保存）
        index_data = self._load_log_index()

        # 最新のエントリを更新
        if index_data["logs"]:
            latest_entry = index_data["logs"][-1]
            if latest_entry["timestamp"] == execution_result.timestamp.isoformat():
                # 詳細な失敗情報を追加
                latest_entry["detailed_failures"] = [
                    {
                        "type": f.type.value,
                        "message": f.message,
                        "file_path": f.file_path,
                        "line_number": f.line_number,
                    }
                    for f in execution_result.all_failures
                ]

                # インデックスファイルに保存
                with open(self.index_file, "w", encoding="utf-8") as f:
                    json.dump(index_data, f, indent=2, ensure_ascii=False)

    def compare_with_previous(self, current_result: ExecutionResult) -> dict[str, Any] | None:
        """現在の実行結果を前回と比較

        Args:
            current_result: 現在の実行結果

        Returns:
            比較結果（前回の実行が存在しない場合はNone）

        """
        previous_result = self.get_previous_execution(current_result.timestamp)

        if not previous_result:
            return None

        from ..core.log_comparator import LogComparator

        comparator = LogComparator()
        comparison = comparator.compare_executions(current_result, previous_result)
        summary = comparator.generate_diff_summary(comparison)

        return {
            "comparison": comparison,
            "summary": summary,
            "has_changes": comparison.has_changes,
            "improvement_score": comparison.improvement_score,
        }
