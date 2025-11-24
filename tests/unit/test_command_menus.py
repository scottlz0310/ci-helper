"""
コマンドメニューのテスト

CommandMenuBuilder クラスの機能をテストします。
"""

from io import StringIO
from unittest.mock import Mock, patch

from rich.console import Console

from ci_helper.ui.command_menus import CommandMenuBuilder
from ci_helper.ui.menu_system import Menu


class TestCommandMenuBuilder:
    """CommandMenuBuilder クラスのテスト"""

    def setup_method(self):
        """テストセットアップ"""
        self.output = StringIO()
        self.console = Console(file=self.output, width=80, legacy_windows=False)

        # モックコマンドハンドラーを作成
        self.command_handlers = {
            "doctor": Mock(return_value=True),
            "init": Mock(return_value=True),
            "test": Mock(return_value=True),
            "analyze": Mock(return_value=True),
            "logs": Mock(return_value=True),
            "secrets": Mock(return_value=True),
            "cache": Mock(return_value=True),
            "clean": Mock(return_value=True),
        }

        self.builder = CommandMenuBuilder(self.console, self.command_handlers)

    def test_builder_initialization(self):
        """ビルダーの初期化をテスト"""
        assert self.builder.console == self.console
        assert self.builder.command_handlers == self.command_handlers

    def test_build_main_menu_structure(self):
        """メインメニューの構造をテスト"""
        main_menu = self.builder.build_main_menu()

        assert isinstance(main_menu, Menu)
        assert main_menu.title == "CI-Helper メインメニュー"
        assert main_menu.show_quit is True
        assert len(main_menu.items) == 8  # 8つのメニュー項目

        # 各メニュー項目の基本構造を確認
        expected_keys = ["1", "2", "3", "4", "5", "6", "7", "8"]
        actual_keys = [item.key for item in main_menu.items]
        assert actual_keys == expected_keys

    def test_main_menu_items_content(self):
        """メインメニュー項目の内容をテスト"""
        main_menu = self.builder.build_main_menu()
        items = main_menu.items

        # 初期設定メニュー
        assert items[0].title == "初期設定"
        assert items[0].submenu is not None
        assert items[0].action is None

        # 環境チェック
        assert items[1].title == "環境チェック"
        assert items[1].action is not None
        assert items[1].submenu is None

        # CI/CDテスト
        assert items[2].title == "CI/CDテスト"
        assert items[2].submenu is not None

        # AI分析
        assert items[3].title == "AI分析"
        assert items[3].submenu is not None

        # ログ管理
        assert items[4].title == "ログ管理"
        assert items[4].submenu is not None

        # シークレット管理
        assert items[5].title == "シークレット管理"
        assert items[5].submenu is not None

        # キャッシュ管理
        assert items[6].title == "キャッシュ管理"
        assert items[6].submenu is not None

        # クリーンアップ
        assert items[7].title == "クリーンアップ"
        assert items[7].action is not None
        assert items[7].submenu is None

    def test_init_submenu_structure(self):
        """初期設定サブメニューの構造をテスト"""
        init_submenu = self.builder._build_init_submenu()

        assert isinstance(init_submenu, Menu)
        assert init_submenu.title == "初期設定メニュー"
        assert init_submenu.show_back is True
        assert init_submenu.show_quit is True
        assert len(init_submenu.items) == 3

        # 各項目の基本構造を確認
        items = init_submenu.items
        assert items[0].title == "対話的初期設定（推奨）"
        assert items[1].title == "標準初期設定"
        assert items[2].title == "環境セットアップ"

    def test_test_submenu_structure(self):
        """テストサブメニューの構造をテスト"""
        test_submenu = self.builder._build_test_submenu()

        assert isinstance(test_submenu, Menu)
        assert test_submenu.title == "CI/CDテストメニュー"
        assert test_submenu.show_back is True
        assert test_submenu.show_quit is True
        assert len(test_submenu.items) == 3

        items = test_submenu.items
        assert items[0].title == "全ワークフロー実行"
        assert items[1].title == "特定ワークフロー実行"
        assert items[2].title == "特定ジョブ実行"

    def test_analyze_submenu_structure(self):
        """AI分析サブメニューの構造をテスト"""
        analyze_submenu = self.builder._build_analyze_submenu()

        assert isinstance(analyze_submenu, Menu)
        assert analyze_submenu.title == "AI分析メニュー"
        assert analyze_submenu.show_back is True
        assert analyze_submenu.show_quit is True
        assert len(analyze_submenu.items) == 3

        items = analyze_submenu.items
        assert items[0].title == "最新ログ分析"
        assert items[1].title == "対話的分析"
        assert items[2].title == "特定ログ分析"

    def test_logs_submenu_structure(self):
        """ログ管理サブメニューの構造をテスト"""
        logs_submenu = self.builder._build_logs_submenu()

        assert isinstance(logs_submenu, Menu)
        assert logs_submenu.title == "ログ管理メニュー"
        assert logs_submenu.show_back is True
        assert logs_submenu.show_quit is True
        assert len(logs_submenu.items) == 4

        items = logs_submenu.items
        assert items[0].title == "ログ一覧表示"
        assert items[1].title == "最新ログ表示"
        assert items[2].title == "ログ比較"
        assert items[3].title == "ログ整形"

        # ログ整形サブメニューの存在確認
        assert items[3].submenu is not None
        assert items[3].submenu.title == "ログ整形メニュー"

    def test_log_formatting_submenu_structure(self):
        """ログ整形サブメニューの構造をテスト"""
        formatting_submenu = self.builder._build_log_formatting_submenu()

        assert isinstance(formatting_submenu, Menu)
        assert formatting_submenu.title == "ログ整形メニュー"
        assert formatting_submenu.show_back is True
        assert formatting_submenu.show_quit is True
        assert len(formatting_submenu.items) == 3

        items = formatting_submenu.items
        assert items[0].title == "最新ログ整形"
        assert items[0].description == "最新の実行ログを様々な形式で整形"
        assert items[1].title == "特定ログ整形"
        assert items[1].description == "指定したログファイルを様々な形式で整形"
        assert items[2].title == "カスタム整形"
        assert items[2].description == "整形パラメータをカスタマイズ"

        # 最新ログ整形と特定ログ整形はサブメニューを持つ
        assert items[0].submenu is not None
        assert items[1].submenu is not None
        # カスタム整形はアクションを持つ
        assert items[2].action is not None

    def test_secrets_submenu_structure(self):
        """シークレット管理サブメニューの構造をテスト"""
        secrets_submenu = self.builder._build_secrets_submenu()

        assert isinstance(secrets_submenu, Menu)
        assert secrets_submenu.title == "シークレット管理メニュー"
        assert secrets_submenu.show_back is True
        assert secrets_submenu.show_quit is True
        assert len(secrets_submenu.items) == 2

        items = secrets_submenu.items
        assert items[0].title == "シークレット検証"
        assert items[1].title == "シークレット一覧"

    def test_cache_submenu_structure(self):
        """キャッシュ管理サブメニューの構造をテスト"""
        cache_submenu = self.builder._build_cache_submenu()

        assert isinstance(cache_submenu, Menu)
        assert cache_submenu.title == "キャッシュ管理メニュー"
        assert cache_submenu.show_back is True
        assert cache_submenu.show_quit is True
        assert len(cache_submenu.items) == 4

        items = cache_submenu.items
        assert items[0].title == "高速プル（推奨）"
        assert items[1].title == "カスタムプル"
        assert items[2].title == "キャッシュ状態表示"
        assert items[3].title == "キャッシュクリア"

    def test_create_command_action_existing_command(self):
        """既存コマンドのアクション作成をテスト"""
        action = self.builder._create_command_action("doctor")

        # アクションを実行
        result = action()

        # コマンドハンドラーが呼び出されることを確認
        self.command_handlers["doctor"].assert_called_once()
        assert result is True

    def test_create_command_action_missing_command(self):
        """存在しないコマンドのアクション作成をテスト"""
        action = self.builder._create_command_action("nonexistent")

        # アクションを実行
        action()

        # エラーメッセージが出力されることを確認
        output = self.output.getvalue()
        assert "コマンド 'nonexistent' が見つかりません" in output

    def test_test_action_execution(self):
        """テストアクションの実行をテスト"""
        action = self.builder._create_test_action()

        result = action()

        self.command_handlers["test"].assert_called_once()
        assert result is True

    def test_test_action_missing_handler(self):
        """テストハンドラーが存在しない場合のテスト"""
        # testハンドラーを削除
        del self.command_handlers["test"]
        builder = CommandMenuBuilder(self.console, self.command_handlers)

        action = builder._create_test_action()
        action()

        output = self.output.getvalue()
        assert "testコマンドが見つかりません" in output

    @patch("ci_helper.utils.workflow_detector.WorkflowDetector")
    @patch("rich.prompt.Prompt.ask")
    def test_test_workflow_action_with_workflows(self, mock_prompt, mock_detector_class):
        """ワークフロー選択アクションのテスト（ワークフローが存在する場合）"""
        # モックワークフローを作成
        mock_workflow = Mock()
        mock_workflow.name = "Test Workflow"
        mock_workflow.filename = "test.yml"
        mock_workflow.jobs = ["test", "build"]

        mock_detector = Mock()
        mock_detector.find_workflows.return_value = [mock_workflow]
        mock_detector.get_workflow_choices.return_value = {"1": mock_workflow}
        mock_detector_class.return_value = mock_detector

        mock_prompt.return_value = "1"

        action = self.builder._create_test_workflow_action()
        action()

        mock_detector.find_workflows.assert_called_once()
        mock_detector.display_workflows.assert_called_once_with([mock_workflow])
        mock_detector.get_workflow_choices.assert_called_once_with([mock_workflow])

    @patch("ci_helper.utils.workflow_detector.WorkflowDetector")
    def test_test_workflow_action_no_workflows(self, mock_detector_class):
        """ワークフロー選択アクション（ワークフローが存在しない場合）"""
        mock_detector = Mock()
        mock_detector.find_workflows.return_value = []
        mock_detector_class.return_value = mock_detector

        action = self.builder._create_test_workflow_action()
        result = action()

        assert result is False
        output = self.output.getvalue()
        assert "ワークフローファイルが見つかりません" in output

    @patch("ci_helper.utils.workflow_detector.WorkflowDetector")
    @patch("rich.prompt.Prompt.ask")
    def test_test_job_action_with_jobs(self, mock_prompt, mock_detector_class):
        """ジョブ選択アクションのテスト（ジョブが存在する場合）"""
        # モックワークフローを作成
        mock_workflow1 = Mock()
        mock_workflow1.name = "Workflow 1"
        mock_workflow1.jobs = ["test", "build"]

        mock_workflow2 = Mock()
        mock_workflow2.name = "Workflow 2"
        mock_workflow2.jobs = ["test", "deploy"]

        mock_detector = Mock()
        mock_detector.find_workflows.return_value = [mock_workflow1, mock_workflow2]
        mock_detector_class.return_value = mock_detector

        mock_prompt.return_value = "1"

        action = self.builder._create_test_job_action()
        action()

        mock_detector.find_workflows.assert_called_once()

    @patch("ci_helper.utils.workflow_detector.WorkflowDetector")
    def test_test_job_action_no_workflows(self, mock_detector_class):
        """ジョブ選択アクション（ワークフローが存在しない場合）"""
        mock_detector = Mock()
        mock_detector.find_workflows.return_value = []
        mock_detector_class.return_value = mock_detector

        action = self.builder._create_test_job_action()
        result = action()

        assert result is False
        output = self.output.getvalue()
        assert "ワークフローファイルが見つかりません" in output

    def test_analyze_action_execution(self):
        """AI分析アクションの実行をテスト"""
        action = self.builder._create_analyze_action()

        result = action()

        self.command_handlers["analyze"].assert_called_once()
        assert result is True

    def test_analyze_interactive_action_missing_handler(self):
        """対話的分析ハンドラーが存在しない場合のテスト"""
        action = self.builder._create_analyze_interactive_action()
        action()

        output = self.output.getvalue()
        assert "対話的分析モードを開始します" in output

    @patch("rich.prompt.Prompt.ask")
    def test_analyze_file_action_with_file(self, mock_prompt):
        """ファイル分析アクションのテスト（ファイル指定あり）"""
        mock_prompt.return_value = "/path/to/log.txt"

        action = self.builder._create_analyze_file_action()
        action()

        output = self.output.getvalue()
        assert "ログファイル '/path/to/log.txt' を分析します" in output

    @patch("rich.prompt.Prompt.ask")
    def test_analyze_file_action_no_file(self, mock_prompt):
        """ファイル分析アクション（ファイル指定なし）"""
        mock_prompt.return_value = ""

        action = self.builder._create_analyze_file_action()
        action()

        output = self.output.getvalue()
        assert "ログファイルパスが入力されませんでした" in output

    @patch("rich.prompt.Prompt.ask")
    def test_logs_compare_action_with_files(self, mock_prompt):
        """ログ比較アクションのテスト（ファイル指定あり）"""
        mock_prompt.side_effect = ["/path/to/log1.txt", "/path/to/log2.txt"]

        action = self.builder._create_logs_compare_action()
        action()

        output = self.output.getvalue()
        assert "'/path/to/log1.txt' と '/path/to/log2.txt' を比較します" in output

    @patch("rich.prompt.Prompt.ask")
    def test_logs_compare_action_missing_files(self, mock_prompt):
        """ログ比較アクション（ファイル指定不足）"""
        mock_prompt.side_effect = ["/path/to/log1.txt", ""]

        action = self.builder._create_logs_compare_action()
        action()

        output = self.output.getvalue()
        assert "両方のログファイルパスを入力してください" in output

    @patch("rich.prompt.Prompt.ask")
    def test_cache_pull_action_default_settings(self, mock_prompt):
        """キャッシュプルアクション（デフォルト設定）"""
        mock_prompt.side_effect = ["60", "default"]

        action = self.builder._create_cache_pull_action()
        action()

        output = self.output.getvalue()
        assert "Dockerイメージをプルします" in output
        assert "ghcr.io/catthehacker/ubuntu:act-latest" in output

    @patch("rich.prompt.Prompt.ask")
    def test_cache_pull_action_custom_timeout(self, mock_prompt):
        """キャッシュプルアクション（カスタムタイムアウト）"""
        mock_prompt.side_effect = ["custom", "90", "minimal"]

        action = self.builder._create_cache_pull_action()
        action()

        output = self.output.getvalue()
        assert "Dockerイメージをプルします" in output

    @patch("rich.prompt.Prompt.ask")
    def test_cache_pull_action_custom_image(self, mock_prompt):
        """キャッシュプルアクション（カスタムイメージ）"""
        mock_prompt.side_effect = ["30", "custom", "my-custom-image:latest"]

        action = self.builder._create_cache_pull_action()
        action()

        output = self.output.getvalue()
        assert "my-custom-image:latest" in output

    def test_cache_quick_pull_action(self):
        """高速キャッシュプルアクションのテスト"""
        action = self.builder._create_cache_quick_pull_action()
        action()

        output = self.output.getvalue()
        assert "高速プルを開始します" in output
        assert "ghcr.io/catthehacker/ubuntu:act-latest" in output

    def test_interactive_init_action_missing_handler(self):
        """対話的初期設定ハンドラーが存在しない場合のテスト"""
        action = self.builder._create_interactive_init_action()
        action()

        output = self.output.getvalue()
        assert "対話的初期設定を開始します" in output

    @patch("rich.prompt.Confirm.ask")
    def test_cache_clear_action_confirmed(self, mock_confirm):
        """キャッシュクリアアクション（確認あり）"""
        mock_confirm.return_value = True

        action = self.builder._create_cache_clear_action()
        action()

        output = self.output.getvalue()
        assert "キャッシュをクリアします" in output

    @patch("rich.prompt.Confirm.ask")
    def test_cache_clear_action_cancelled(self, mock_confirm):
        """キャッシュクリアアクション（キャンセル）"""
        mock_confirm.return_value = False

        action = self.builder._create_cache_clear_action()
        action()

        output = self.output.getvalue()
        assert "キャッシュクリアがキャンセルされました" in output
