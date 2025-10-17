"""
エラー復旧ガイドのユニットテスト
"""

from unittest.mock import patch

from ci_helper.utils.recovery_guide import RecoveryGuide


class TestRecoveryGuide:
    """RecoveryGuide クラスのテスト"""

    @patch("platform.system")
    def test_get_act_installation_guide_macos(self, mock_system):
        """macOS用actインストールガイドテスト"""
        mock_system.return_value = "Darwin"

        guide = RecoveryGuide.get_act_installation_guide()

        assert "macOS" in guide
        assert "brew install act" in guide
        assert "Homebrew" in guide
        assert "act --version" in guide

    @patch("platform.system")
    def test_get_act_installation_guide_linux(self, mock_system):
        """Linux用actインストールガイドテスト"""
        mock_system.return_value = "Linux"

        guide = RecoveryGuide.get_act_installation_guide()

        assert "Linux" in guide
        assert "GitHub Releases" in guide
        assert "tar -xzf" in guide
        assert "act --version" in guide

    @patch("platform.system")
    def test_get_act_installation_guide_windows(self, mock_system):
        """Windows用actインストールガイドテスト"""
        mock_system.return_value = "Windows"

        guide = RecoveryGuide.get_act_installation_guide()

        assert "Windows" in guide
        assert "Chocolatey" in guide
        assert "Scoop" in guide
        assert "choco install act-cli" in guide
        assert "scoop install act" in guide

    @patch("platform.system")
    def test_get_act_installation_guide_unknown_os(self, mock_system):
        """未知のOS用actインストールガイドテスト"""
        mock_system.return_value = "UnknownOS"

        guide = RecoveryGuide.get_act_installation_guide()

        assert "GitHub Releases" in guide
        assert "act --version" in guide

    @patch("platform.system")
    def test_get_docker_installation_guide_macos(self, mock_system):
        """macOS用Dockerインストールガイドテスト"""
        mock_system.return_value = "Darwin"

        guide = RecoveryGuide.get_docker_installation_guide()

        assert "macOS" in guide
        assert "Docker Desktop" in guide
        assert "brew install --cask docker" in guide
        assert "docker --version" in guide
        assert "docker info" in guide

    @patch("platform.system")
    def test_get_docker_installation_guide_linux(self, mock_system):
        """Linux用Dockerインストールガイドテスト"""
        mock_system.return_value = "Linux"

        guide = RecoveryGuide.get_docker_installation_guide()

        assert "Linux" in guide
        assert "Ubuntu/Debian" in guide
        assert "apt-get install" in guide
        assert "docker-ce" in guide
        assert "systemctl start docker" in guide

    @patch("platform.system")
    def test_get_docker_installation_guide_windows(self, mock_system):
        """Windows用Dockerインストールガイドテスト"""
        mock_system.return_value = "Windows"

        guide = RecoveryGuide.get_docker_installation_guide()

        assert "Windows" in guide
        assert "Docker Desktop" in guide
        assert "WSL 2" in guide
        assert "PowerShell" in guide

    @patch("platform.system")
    def test_get_docker_installation_guide_unknown_os(self, mock_system):
        """未知のOS用Dockerインストールガイドテスト"""
        mock_system.return_value = "UnknownOS"

        guide = RecoveryGuide.get_docker_installation_guide()

        assert "docs.docker.com" in guide
        assert "docker --version" in guide

    def test_get_workflow_setup_guide(self):
        """ワークフローセットアップガイドテスト"""
        guide = RecoveryGuide.get_workflow_setup_guide()

        assert "GitHub Actions" in guide
        assert ".github/workflows" in guide
        assert "mkdir -p" in guide
        assert "ci.yml" in guide
        assert "python.yml" in guide
        assert "actions/checkout@v4" in guide

    def test_get_disk_space_cleanup_guide(self):
        """ディスク容量クリーンアップガイドテスト"""
        guide = RecoveryGuide.get_disk_space_cleanup_guide()

        assert "ci-run clean" in guide
        assert "docker system prune" in guide
        assert "Linux/macOS" in guide
        assert "Windows" in guide
        assert "df -h" in guide
        assert "cleanmgr" in guide

    def test_get_troubleshooting_guide(self):
        """トラブルシューティングガイドテスト"""
        guide = RecoveryGuide.get_troubleshooting_guide()

        assert "act: command not found" in guide
        assert "Docker daemon" in guide
        assert "Permission denied" in guide
        assert "Out of memory" in guide
        assert "ci-run doctor" in guide
        assert "ci-run logs" in guide

    @patch("ci_helper.utils.recovery_guide.console")
    def test_display_recovery_guide_act(self, mock_console):
        """actガイド表示テスト"""
        RecoveryGuide.display_recovery_guide("act")

        mock_console.print.assert_called_once()
        # Panel が作成されて表示されることを確認
        call_args = mock_console.print.call_args[0][0]
        assert hasattr(call_args, "title")

    @patch("ci_helper.utils.recovery_guide.console")
    def test_display_recovery_guide_docker(self, mock_console):
        """Dockerガイド表示テスト"""
        RecoveryGuide.display_recovery_guide("docker")

        mock_console.print.assert_called_once()

    @patch("ci_helper.utils.recovery_guide.console")
    def test_display_recovery_guide_workflows(self, mock_console):
        """ワークフローガイド表示テスト"""
        RecoveryGuide.display_recovery_guide("workflows")

        mock_console.print.assert_called_once()

    @patch("ci_helper.utils.recovery_guide.console")
    def test_display_recovery_guide_disk_space(self, mock_console):
        """ディスク容量ガイド表示テスト"""
        RecoveryGuide.display_recovery_guide("disk_space")

        mock_console.print.assert_called_once()

    @patch("ci_helper.utils.recovery_guide.console")
    def test_display_recovery_guide_troubleshooting(self, mock_console):
        """トラブルシューティングガイド表示テスト"""
        RecoveryGuide.display_recovery_guide("troubleshooting")

        mock_console.print.assert_called_once()

    @patch("ci_helper.utils.recovery_guide.console")
    def test_display_recovery_guide_invalid_type(self, mock_console):
        """無効なガイドタイプのテスト"""
        RecoveryGuide.display_recovery_guide("invalid_type")

        mock_console.print.assert_called_once()
        # エラーメッセージが表示されることを確認
        call_args = mock_console.print.call_args[0][0]
        assert "不明なガイドタイプ" in call_args

    def test_get_quick_fixes(self):
        """クイックフィックス取得テスト"""
        fixes = RecoveryGuide.get_quick_fixes()

        assert isinstance(fixes, dict)

        # 各問題タイプが含まれることを確認
        expected_keys = ["act_not_found", "docker_not_running", "no_workflows", "permission_denied", "disk_space_low"]

        for key in expected_keys:
            assert key in fixes
            assert isinstance(fixes[key], list)
            assert len(fixes[key]) > 0

    def test_get_quick_fixes_act_not_found(self):
        """act未発見のクイックフィックステスト"""
        fixes = RecoveryGuide.get_quick_fixes()
        act_fixes = fixes["act_not_found"]

        assert any("brew install act" in fix for fix in act_fixes)
        assert any("PATH" in fix for fix in act_fixes)
        assert any("ターミナルを再起動" in fix for fix in act_fixes)

    def test_get_quick_fixes_docker_not_running(self):
        """Docker未実行のクイックフィックステスト"""
        fixes = RecoveryGuide.get_quick_fixes()
        docker_fixes = fixes["docker_not_running"]

        assert any("Docker Desktop" in fix for fix in docker_fixes)
        assert any("systemctl" in fix for fix in docker_fixes)

    def test_get_quick_fixes_no_workflows(self):
        """ワークフロー未発見のクイックフィックステスト"""
        fixes = RecoveryGuide.get_quick_fixes()
        workflow_fixes = fixes["no_workflows"]

        assert any(".github/workflows" in fix for fix in workflow_fixes)
        assert any(".yml/.yaml" in fix for fix in workflow_fixes)

    def test_get_quick_fixes_permission_denied(self):
        """権限エラーのクイックフィックステスト"""
        fixes = RecoveryGuide.get_quick_fixes()
        permission_fixes = fixes["permission_denied"]

        assert any("ls -la" in fix for fix in permission_fixes)
        assert any("chmod" in fix for fix in permission_fixes)
        assert any("sudo" in fix for fix in permission_fixes)

    def test_get_quick_fixes_disk_space_low(self):
        """ディスク容量不足のクイックフィックステスト"""
        fixes = RecoveryGuide.get_quick_fixes()
        disk_fixes = fixes["disk_space_low"]

        assert any("ci-run clean" in fix for fix in disk_fixes)
        assert any("docker system prune" in fix for fix in disk_fixes)
        assert any("一時ファイル" in fix for fix in disk_fixes)


class TestRecoveryGuideContent:
    """復旧ガイド内容の詳細テスト"""

    def test_act_guide_contains_essential_info(self):
        """actガイドに必要な情報が含まれることのテスト"""
        with patch("platform.system", return_value="Darwin"):
            guide = RecoveryGuide.get_act_installation_guide()

            # 必要な要素が含まれることを確認
            assert "brew install act" in guide
            assert "GitHub Releases" in guide
            assert "/usr/local/bin" in guide
            assert "act --version" in guide

    def test_docker_guide_contains_essential_info(self):
        """Dockerガイドに必要な情報が含まれることのテスト"""
        with patch("platform.system", return_value="Linux"):
            guide = RecoveryGuide.get_docker_installation_guide()

            # 必要な要素が含まれることを確認
            assert "docker-ce" in guide
            assert "apt-get" in guide
            assert "systemctl" in guide
            assert "usermod -aG docker" in guide

    def test_workflow_guide_contains_sample_workflows(self):
        """ワークフローガイドにサンプルが含まれることのテスト"""
        guide = RecoveryGuide.get_workflow_setup_guide()

        # サンプルワークフローが含まれることを確認
        assert "name: CI" in guide
        assert "name: Python CI" in guide
        assert "actions/checkout@v4" in guide
        assert "actions/setup-node@v4" in guide
        assert "actions/setup-python@v4" in guide

    def test_cleanup_guide_contains_commands(self):
        """クリーンアップガイドにコマンドが含まれることのテスト"""
        guide = RecoveryGuide.get_disk_space_cleanup_guide()

        # 各種クリーンアップコマンドが含まれることを確認
        assert "ci-run clean --logs-only" in guide
        assert "ci-run clean --all" in guide
        assert "docker system prune -a" in guide
        assert "journalctl --vacuum-time" in guide

    def test_troubleshooting_guide_contains_scenarios(self):
        """トラブルシューティングガイドにシナリオが含まれることのテスト"""
        guide = RecoveryGuide.get_troubleshooting_guide()

        # 各種トラブルシューティングシナリオが含まれることを確認
        assert "act: command not found" in guide
        assert "Cannot connect to the Docker daemon" in guide
        assert "No workflow files found" in guide
        assert "Permission denied" in guide
        assert "Out of memory" in guide
