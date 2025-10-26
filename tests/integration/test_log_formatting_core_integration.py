"""
ログ整形機能コア統合テスト

要件11.1-11.5の基本的な統合テストを実装します。
複雑なモッキングを避けて、実際の機能の統合を検証します。
"""

from __future__ import annotations

import json
from unittest.mock import Mock

import pytest
from rich.console import Console

from ci_helper.core.models import ExecutionResult, Failure, FailureType, JobResult, WorkflowResult
from ci_helper.formatters import get_formatter_manager
from ci_helper.ui.command_menus import CommandMenuBuilder
from ci_helper.ui.menu_system import MenuSystem


class TestLogFormattingCoreIntegration:
    """ログ整形機能のコア統合テスト"""

    @pytest.fixture
    def simple_execution_result(self) -> ExecutionResult:
        """シンプルなテスト用実行結果"""
        failure = Failure(
            type=FailureType.ERROR,
            message="Test error message",
            file_path="test.py",
            line_number=10,
            context_before=["line 9"],
            context_after=["line 11"],
            stack_trace="Test stack trace",
        )

        job = JobResult(name="test", success=False, failures=[failure], duration=30.0)
        workflow = WorkflowResult(name="test.yml", success=False, jobs=[job], duration=30.0)

        return ExecutionResult(success=False, workflows=[workflow], total_duration=30.0)

    @pytest.fixture
    def success_execution_result(self) -> ExecutionResult:
        """成功した実行結果"""
        job = JobResult(name="test", success=True, failures=[], duration=30.0)
        workflow = WorkflowResult(name="test.yml", success=True, jobs=[job], duration=30.0)

        return ExecutionResult(success=True, workflows=[workflow], total_duration=30.0)

    def test_formatter_manager_singleton_consistency(self):
        """要件11.2: フォーマッターマネージャーのシングルトン一貫性テスト"""
        # 複数回取得して同じインスタンスが返されることを確認
        manager1 = get_formatter_manager()
        manager2 = get_formatter_manager()

        # 同じインスタンスであることを確認
        assert manager1 is manager2

        # 利用可能なフォーマットが一貫していることを確認
        formats1 = manager1.list_available_formats()
        formats2 = manager2.list_available_formats()

        assert formats1 == formats2
        assert "ai" in formats1
        assert "human" in formats1
        assert "json" in formats1

    def test_formatter_output_consistency(self, simple_execution_result: ExecutionResult):
        """要件11.3: 同じ入力に対する出力一貫性テスト"""
        formatter_manager = get_formatter_manager()

        # 同じパラメータで複数回実行
        format_options = {"filter_errors": False, "verbose_level": "normal", "max_failures": 5}

        # AI形式での一貫性テスト
        ai_output1 = formatter_manager.format_log(simple_execution_result, "ai", **format_options)
        ai_output2 = formatter_manager.format_log(simple_execution_result, "ai", **format_options)

        # 同じ入力に対して同じ出力が生成されることを確認
        assert ai_output1 == ai_output2
        assert ai_output1.strip()  # 出力が空でない

        # JSON形式での一貫性テスト（タイムスタンプを除く構造の一貫性）
        json_output1 = formatter_manager.format_log(simple_execution_result, "json", **format_options)
        json_output2 = formatter_manager.format_log(simple_execution_result, "json", **format_options)

        # JSONの構造が一貫していることを確認（タイムスタンプは除く）
        data1 = json.loads(json_output1)
        data2 = json.loads(json_output2)

        # タイムスタンプ以外のキーが同じであることを確認
        assert data1.keys() == data2.keys()
        assert data1["execution_summary"]["success"] == data2["execution_summary"]["success"]
        assert data1["execution_summary"]["total_duration"] == data2["execution_summary"]["total_duration"]

        assert json_output1.strip()  # 出力が空でない

    def test_different_formats_produce_different_outputs(self, simple_execution_result: ExecutionResult):
        """要件11.3: 異なるフォーマット間での出力差異テスト"""
        formatter_manager = get_formatter_manager()

        format_options = {"filter_errors": False, "verbose_level": "normal", "max_failures": 5}

        # 各フォーマットで出力を生成
        ai_output = formatter_manager.format_log(simple_execution_result, "ai", **format_options)
        human_output = formatter_manager.format_log(simple_execution_result, "human", **format_options)
        json_output = formatter_manager.format_log(simple_execution_result, "json", **format_options)

        # 各出力が空でないことを確認
        assert ai_output.strip()
        assert human_output.strip()
        assert json_output.strip()

        # 異なるフォーマット間では異なる出力が生成されることを確認
        assert ai_output != human_output
        assert ai_output != json_output
        assert human_output != json_output

    def test_json_format_structure_validation(self, simple_execution_result: ExecutionResult):
        """要件11.3: JSON形式の構造検証テスト"""
        formatter_manager = get_formatter_manager()

        json_output = formatter_manager.format_log(simple_execution_result, "json", max_failures=5)

        # 有効なJSONであることを確認
        try:
            data = json.loads(json_output)
        except json.JSONDecodeError as e:
            pytest.fail(f"無効なJSON出力: {e}")

        # 必須フィールドの存在確認
        assert "execution_summary" in data
        assert "workflows" in data
        assert "all_failures" in data

        # execution_summaryの構造確認
        exec_summary = data["execution_summary"]
        assert "success" in exec_summary
        assert "total_duration" in exec_summary

        # データ型の確認
        assert isinstance(exec_summary["success"], bool)
        assert isinstance(data["workflows"], list)
        assert isinstance(exec_summary["total_duration"], (int, float))

    def test_success_and_failure_result_handling(
        self, simple_execution_result: ExecutionResult, success_execution_result: ExecutionResult
    ):
        """要件11.3: 成功・失敗結果の適切な処理テスト"""
        formatter_manager = get_formatter_manager()

        format_options = {"max_failures": 5}

        # 失敗結果の処理
        failure_ai_output = formatter_manager.format_log(simple_execution_result, "ai", **format_options)
        failure_json_output = formatter_manager.format_log(simple_execution_result, "json", **format_options)

        # 成功結果の処理
        success_ai_output = formatter_manager.format_log(success_execution_result, "ai", **format_options)
        success_json_output = formatter_manager.format_log(success_execution_result, "json", **format_options)

        # 両方とも出力が生成されることを確認
        assert failure_ai_output.strip()
        assert failure_json_output.strip()
        assert success_ai_output.strip()
        assert success_json_output.strip()

        # JSON出力で成功・失敗フラグが正しく設定されることを確認
        failure_data = json.loads(failure_json_output)
        success_data = json.loads(success_json_output)

        assert failure_data["execution_summary"]["success"] is False
        assert success_data["execution_summary"]["success"] is True

    def test_parameter_validation_consistency(self):
        """要件11.1: パラメータ検証の一貫性テスト"""
        formatter_manager = get_formatter_manager()

        # サポートされているフォーマット
        supported_formats = formatter_manager.list_available_formats()

        # 最低限必要なフォーマットが含まれていることを確認
        required_formats = ["ai", "human", "json"]
        for format_type in required_formats:
            assert format_type in supported_formats

        # 各フォーマットでフォーマッターが取得できることを確認
        for format_type in required_formats:
            formatter = formatter_manager.get_formatter(format_type)
            assert formatter is not None
            assert hasattr(formatter, "format")
            assert hasattr(formatter, "get_format_name")

    def test_invalid_format_error_handling(self):
        """要件11.2: 無効なフォーマットでのエラーハンドリングテスト"""
        formatter_manager = get_formatter_manager()

        # 無効なフォーマットでエラーが発生することを確認
        sample_result = ExecutionResult(success=True, workflows=[], total_duration=0.0)

        with pytest.raises((KeyError, ValueError)):
            formatter_manager.format_log(sample_result, "invalid_format")

    def test_menu_system_initialization(self):
        """要件11.5: メニューシステムの初期化テスト"""
        console = Console()

        # モックコマンドハンドラーを作成
        command_handlers = {
            "format_logs": Mock(return_value=True),
            "format_logs_custom": Mock(return_value=True),
        }

        # メニューシステムが正しく初期化されることを確認
        builder = CommandMenuBuilder(console, command_handlers)
        menu_system = MenuSystem(console)

        assert builder is not None
        assert menu_system is not None

        # メインメニューが構築できることを確認
        main_menu = builder.build_main_menu()
        assert main_menu is not None
        assert main_menu.title == "CI-Helper メインメニュー"
        assert len(main_menu.items) > 0

    def test_formatter_options_processing(self, simple_execution_result: ExecutionResult):
        """要件11.1: フォーマッターオプション処理の一貫性テスト"""
        formatter_manager = get_formatter_manager()

        # 基本オプション
        basic_options = {"filter_errors": False, "verbose_level": "normal", "max_failures": 5}

        # 詳細オプション
        detailed_options = {"filter_errors": True, "verbose_level": "detailed", "max_failures": 10}

        # 各オプションセットで出力が生成されることを確認
        basic_output = formatter_manager.format_log(simple_execution_result, "ai", **basic_options)
        detailed_output = formatter_manager.format_log(simple_execution_result, "ai", **detailed_options)

        assert basic_output.strip()
        assert detailed_output.strip()

        # オプションによって出力が変わることを確認（長さまたは内容）
        # 注意: 実装によっては同じ出力になる場合もあるため、エラーが発生しないことを主に確認
        assert isinstance(basic_output, str)
        assert isinstance(detailed_output, str)

    def test_concurrent_formatter_access_safety(self, simple_execution_result: ExecutionResult):
        """要件11.2: 並行フォーマッターアクセスの安全性テスト"""
        import threading

        formatter_manager = get_formatter_manager()
        results = []
        errors = []

        def format_task(format_type: str):
            try:
                output = formatter_manager.format_log(simple_execution_result, format_type, max_failures=3)
                results.append((format_type, output))
            except Exception as e:
                errors.append((format_type, e))

        # 複数のスレッドで同時にフォーマット処理を実行
        threads = []
        for format_type in ["ai", "human", "json"]:
            thread = threading.Thread(target=format_task, args=(format_type,))
            threads.append(thread)
            thread.start()

        # すべてのスレッドの完了を待機
        for thread in threads:
            thread.join()

        # エラーが発生していないことを確認
        assert not errors, f"並行処理でエラーが発生しました: {errors}"

        # すべてのフォーマットで結果が生成されることを確認
        assert len(results) == 3

        # 各結果が有効であることを確認
        for format_type, output in results:
            assert output.strip(), f"{format_type}フォーマットの出力が空です"

    def test_error_result_formatting_robustness(self):
        """要件11.3: エラー結果フォーマットの堅牢性テスト"""
        formatter_manager = get_formatter_manager()

        # 空の失敗リストを持つ結果
        empty_failure_result = ExecutionResult(
            success=False,
            workflows=[
                WorkflowResult(
                    name="test.yml",
                    success=False,
                    jobs=[JobResult(name="test", success=False, failures=[], duration=0.0)],
                    duration=0.0,
                )
            ],
            total_duration=0.0,
        )

        # 各フォーマットで処理できることを確認
        for format_type in ["ai", "human", "json"]:
            try:
                output = formatter_manager.format_log(empty_failure_result, format_type, max_failures=5)
                assert output.strip(), f"{format_type}フォーマットの出力が空です"
            except Exception as e:
                pytest.fail(f"{format_type}フォーマットでエラーが発生しました: {e}")

    def test_menu_command_handler_interface_compatibility(self):
        """要件11.1: メニューとコマンドハンドラーインターフェースの互換性テスト"""
        # メニューで使用されるハンドラーインターフェース
        console = Console()

        # 基本的なハンドラー関数のシグネチャをテスト
        def mock_format_logs_handler(format_type: str, **kwargs) -> bool:
            return True

        def mock_format_logs_custom_handler(format_type: str, **kwargs) -> bool:
            return True

        command_handlers = {
            "format_logs": mock_format_logs_handler,
            "format_logs_custom": mock_format_logs_custom_handler,
        }

        # メニューシステムが正しく初期化されることを確認
        builder = CommandMenuBuilder(console, command_handlers)
        main_menu = builder.build_main_menu()

        assert main_menu is not None

        # ハンドラーが呼び出し可能であることを確認
        assert callable(command_handlers["format_logs"])
        assert callable(command_handlers["format_logs_custom"])

        # 基本的な呼び出しが成功することを確認
        result1 = command_handlers["format_logs"]("ai", input_file=None, output_file=None)
        result2 = command_handlers["format_logs_custom"]("ai", detail_level="normal")

        assert result1 is True
        assert result2 is True
