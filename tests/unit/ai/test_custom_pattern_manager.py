"""
custom_pattern_manager.py のテスト

カスタムパターン管理システムの機能をテストします。
"""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pytest
from ci_helper.ai.custom_pattern_manager import CustomPatternManager
from ci_helper.ai.exceptions import ConfigurationError, ValidationError
from ci_helper.ai.models import Pattern
from ci_helper.utils.config import Config


class TestCustomPatternManager:
    """CustomPatternManager のテストクラス"""

    @pytest.fixture
    def mock_config(self):
        """モック設定オブジェクト"""
        config = Mock(spec=Config)
        config.get_pattern_database_path.return_value = Path("/test/patterns")
        return config

    @pytest.fixture
    def pattern_manager(self, mock_config):
        """CustomPatternManager インスタンス"""
        return CustomPatternManager(mock_config)

    @pytest.fixture
    def sample_pattern_data(self):
        """サンプルパターンデータ"""
        return {
            "name": "テストパターン",
            "category": "test",
            "regex_patterns": [r"error:\s+(.+)"],
            "keywords": ["error", "failed"],
            "context_requirements": ["test context"],
            "confidence_base": 0.8,
        }

    @pytest.fixture
    def sample_pattern(self):
        """サンプルPatternオブジェクト"""
        return Pattern(
            id="test_pattern_001",
            name="テストパターン",
            category="test",
            regex_patterns=[r"error:\s+(.+)"],
            keywords=["error", "failed"],
            context_requirements=["test context"],
            confidence_base=0.8,
            success_rate=0.0,
            created_at=datetime(2024, 1, 1, 12, 0, 0),
            updated_at=datetime(2024, 1, 1, 12, 0, 0),
            user_defined=True,
        )

    def test_init(self, mock_config):
        """初期化のテスト"""
        manager = CustomPatternManager(mock_config)

        assert manager.config == mock_config
        assert manager.custom_patterns_dir == Path("/test/patterns/custom")
        assert manager.custom_patterns_file == Path("/test/patterns/custom/user_patterns.json")

    @patch("uuid.uuid4")
    @patch("datetime.datetime")
    def test_create_custom_pattern_success(self, mock_datetime, mock_uuid, pattern_manager, sample_pattern_data):
        """カスタムパターン作成成功のテスト"""
        mock_uuid.return_value.hex = "abcd1234" * 4
        mock_datetime.now.return_value = datetime(2024, 1, 1, 12, 0, 0)

        with patch.object(pattern_manager, "_save_custom_pattern") as mock_save:
            pattern = pattern_manager.create_custom_pattern(**sample_pattern_data)

            assert pattern.id == "custom_abcd1234"
            assert pattern.name == "テストパターン"
            assert pattern.category == "test"
            assert pattern.regex_patterns == [r"error:\s+(.+)"]
            assert pattern.keywords == ["error", "failed"]
            assert pattern.context_requirements == ["test context"]
            assert pattern.confidence_base == 0.8
            assert pattern.success_rate == 0.0
            assert pattern.user_defined is True
            mock_save.assert_called_once_with(pattern)

    def test_create_custom_pattern_validation_error(self, pattern_manager):
        """カスタムパターン作成時の検証エラーテスト"""
        with pytest.raises(ValidationError) as exc_info:
            pattern_manager.create_custom_pattern(
                name="",  # 空の名前
                category="test",
                regex_patterns=[r"error:\s+(.+)"],
                keywords=["error"],
            )

        assert "パターン名は空でない文字列である必要があります" in str(exc_info.value)

    def test_create_custom_pattern_invalid_regex(self, pattern_manager):
        """無効な正規表現でのパターン作成テスト"""
        with pytest.raises(ValidationError) as exc_info:
            pattern_manager.create_custom_pattern(
                name="テストパターン",
                category="test",
                regex_patterns=["[invalid regex"],  # 無効な正規表現
                keywords=["error"],
            )

        assert "無効な正規表現パターンです" in str(exc_info.value)

    @patch("pathlib.Path.exists", return_value=False)
    def test_load_custom_patterns_no_file(self, mock_exists, pattern_manager):
        """パターンファイルが存在しない場合の読み込みテスト"""
        patterns = pattern_manager.load_custom_patterns()

        assert patterns == []

    @patch("pathlib.Path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open)
    def test_load_custom_patterns_success(self, mock_file, mock_exists, pattern_manager, sample_pattern):
        """カスタムパターン読み込み成功のテスト"""
        patterns_data = {
            "patterns": [
                {
                    "id": sample_pattern.id,
                    "name": sample_pattern.name,
                    "category": sample_pattern.category,
                    "regex_patterns": sample_pattern.regex_patterns,
                    "keywords": sample_pattern.keywords,
                    "context_requirements": sample_pattern.context_requirements,
                    "confidence_base": sample_pattern.confidence_base,
                    "success_rate": sample_pattern.success_rate,
                    "created_at": sample_pattern.created_at.isoformat(),
                    "updated_at": sample_pattern.updated_at.isoformat(),
                    "user_defined": sample_pattern.user_defined,
                }
            ]
        }

        mock_file.return_value.read.return_value = json.dumps(patterns_data)

        patterns = pattern_manager.load_custom_patterns()

        assert len(patterns) == 1
        pattern = patterns[0]
        assert pattern.id == sample_pattern.id
        assert pattern.name == sample_pattern.name
        assert pattern.category == sample_pattern.category

    @patch("pathlib.Path.exists", return_value=True)
    @patch("builtins.open", side_effect=json.JSONDecodeError("Invalid JSON", "", 0))
    def test_load_custom_patterns_json_error(self, mock_file, mock_exists, pattern_manager):
        """パターン読み込み時のJSONエラーテスト"""
        with pytest.raises(ConfigurationError) as exc_info:
            pattern_manager.load_custom_patterns()

        assert "カスタムパターンの読み込みに失敗しました" in str(exc_info.value)

    def test_update_custom_pattern_success(self, pattern_manager, sample_pattern):
        """カスタムパターン更新成功のテスト"""
        with (
            patch.object(pattern_manager, "load_custom_patterns", return_value=[sample_pattern]),
            patch.object(pattern_manager, "_save_all_custom_patterns") as mock_save,
        ):
            updated_pattern = pattern_manager.update_custom_pattern(
                sample_pattern.id, name="更新されたパターン", confidence_base=0.9
            )

            assert updated_pattern.name == "更新されたパターン"
            assert updated_pattern.confidence_base == 0.9
            mock_save.assert_called_once()

    def test_update_custom_pattern_not_found(self, pattern_manager):
        """存在しないパターンの更新テスト"""
        with patch.object(pattern_manager, "load_custom_patterns", return_value=[]):
            with pytest.raises(ValidationError) as exc_info:
                pattern_manager.update_custom_pattern("nonexistent_id", name="新しい名前")

            assert "カスタムパターンが見つかりません" in str(exc_info.value)

    def test_delete_custom_pattern_success(self, pattern_manager, sample_pattern):
        """カスタムパターン削除成功のテスト"""
        with (
            patch.object(pattern_manager, "load_custom_patterns", return_value=[sample_pattern]),
            patch.object(pattern_manager, "_save_all_custom_patterns") as mock_save,
        ):
            result = pattern_manager.delete_custom_pattern(sample_pattern.id)

            assert result is True
            mock_save.assert_called_once()

    def test_delete_custom_pattern_not_found(self, pattern_manager):
        """存在しないパターンの削除テスト"""
        with patch.object(pattern_manager, "load_custom_patterns", return_value=[]):
            result = pattern_manager.delete_custom_pattern("nonexistent_id")

            assert result is False

    @patch("pathlib.Path.mkdir")
    @patch("builtins.open", new_callable=mock_open)
    def test_export_patterns_success(self, mock_file, mock_mkdir, pattern_manager, sample_pattern):
        """パターンエクスポート成功のテスト"""
        output_file = Path("/test/export.json")

        with (
            patch.object(pattern_manager, "load_custom_patterns", return_value=[sample_pattern]),
            patch("datetime.datetime") as mock_datetime,
        ):
            mock_datetime.now.return_value.isoformat.return_value = "2024-01-01T12:00:00"

            pattern_manager.export_patterns(output_file)

            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
            mock_file.assert_called_once()

    @patch("pathlib.Path.mkdir", side_effect=PermissionError("Permission denied"))
    def test_export_patterns_permission_error(self, mock_mkdir, pattern_manager, sample_pattern):
        """パターンエクスポート時の権限エラーテスト"""
        output_file = Path("/test/export.json")

        with patch.object(pattern_manager, "load_custom_patterns", return_value=[sample_pattern]):
            with pytest.raises(ConfigurationError) as exc_info:
                pattern_manager.export_patterns(output_file)

            assert "パターンのエクスポートに失敗しました" in str(exc_info.value)

    @patch("pathlib.Path.exists", return_value=False)
    def test_import_patterns_file_not_found(self, mock_exists, pattern_manager):
        """インポートファイルが存在しない場合のテスト"""
        import_file = Path("/test/import.json")

        with pytest.raises(ConfigurationError) as exc_info:
            pattern_manager.import_patterns(import_file)

        assert "インポートファイルが見つかりません" in str(exc_info.value)

    @patch("pathlib.Path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open)
    def test_import_patterns_success(self, mock_file, mock_exists, pattern_manager, sample_pattern):
        """パターンインポート成功のテスト"""
        import_file = Path("/test/import.json")
        import_data = {
            "patterns": [
                {
                    "id": sample_pattern.id,
                    "name": sample_pattern.name,
                    "category": sample_pattern.category,
                    "regex_patterns": sample_pattern.regex_patterns,
                    "keywords": sample_pattern.keywords,
                    "context_requirements": sample_pattern.context_requirements,
                    "confidence_base": sample_pattern.confidence_base,
                    "success_rate": sample_pattern.success_rate,
                    "created_at": sample_pattern.created_at.isoformat(),
                    "updated_at": sample_pattern.updated_at.isoformat(),
                    "user_defined": sample_pattern.user_defined,
                }
            ]
        }

        mock_file.return_value.read.return_value = json.dumps(import_data)

        with (
            patch.object(pattern_manager, "load_custom_patterns", return_value=[]),
            patch.object(pattern_manager, "_save_all_custom_patterns") as mock_save,
        ):
            imported_patterns = pattern_manager.import_patterns(import_file)

            assert len(imported_patterns) == 1
            assert imported_patterns[0].name == sample_pattern.name
            mock_save.assert_called_once()

    @patch("pathlib.Path.exists", return_value=True)
    @patch("builtins.open", side_effect=json.JSONDecodeError("Invalid JSON", "", 0))
    def test_import_patterns_json_error(self, mock_file, mock_exists, pattern_manager):
        """パターンインポート時のJSONエラーテスト"""
        import_file = Path("/test/import.json")

        with pytest.raises(ConfigurationError) as exc_info:
            pattern_manager.import_patterns(import_file)

        assert "インポートファイルの読み込みに失敗しました" in str(exc_info.value)

    def test_validate_pattern_integration_success(self, pattern_manager, sample_pattern):
        """パターン統合検証成功のテスト"""
        patterns = [sample_pattern]

        result = pattern_manager.validate_pattern_integration(patterns)

        assert result["valid"] is True
        assert result["pattern_count"] == 1
        assert result["category_distribution"]["test"] == 1
        assert result["duplicate_names"] == []
        assert result["conflicting_patterns"] == []

    def test_validate_pattern_integration_duplicate_names(self, pattern_manager, sample_pattern):
        """重複名パターンの統合検証テスト"""
        pattern2 = Pattern(
            id="test_pattern_002",
            name=sample_pattern.name,  # 同じ名前
            category="test2",
            regex_patterns=[r"warning:\s+(.+)"],
            keywords=["warning"],
            context_requirements=[],
            confidence_base=0.7,
            success_rate=0.0,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            user_defined=True,
        )

        patterns = [sample_pattern, pattern2]

        result = pattern_manager.validate_pattern_integration(patterns)

        assert result["duplicate_names"] == [sample_pattern.name]
        assert len(result["warnings"]) > 0

    def test_validate_pattern_data_success(self, pattern_manager):
        """パターンデータ検証成功のテスト"""
        # 例外が発生しないことを確認
        pattern_manager._validate_pattern_data(
            name="テストパターン",
            category="test",
            regex_patterns=[r"error:\s+(.+)"],
            keywords=["error"],
            confidence_base=0.8,
        )

    def test_validate_pattern_data_invalid_confidence(self, pattern_manager):
        """無効な信頼度でのパターンデータ検証テスト"""
        with pytest.raises(ValidationError) as exc_info:
            pattern_manager._validate_pattern_data(
                name="テストパターン",
                category="test",
                regex_patterns=[r"error:\s+(.+)"],
                keywords=["error"],
                confidence_base=1.5,  # 無効な信頼度
            )

        assert "基本信頼度は0.0から1.0の間の数値である必要があります" in str(exc_info.value)

    @patch("pathlib.Path.mkdir")
    @patch("builtins.open", new_callable=mock_open)
    @patch("datetime.datetime")
    def test_save_all_custom_patterns_success(
        self, mock_datetime, mock_file, mock_mkdir, pattern_manager, sample_pattern
    ):
        """全カスタムパターン保存成功のテスト"""
        mock_datetime.now.return_value.isoformat.return_value = "2024-01-01T12:00:00"

        patterns = [sample_pattern]

        pattern_manager._save_all_custom_patterns(patterns)

        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_file.assert_called_once()

    @patch("pathlib.Path.mkdir")
    @patch("builtins.open", side_effect=PermissionError("Permission denied"))
    def test_save_all_custom_patterns_permission_error(self, mock_file, mock_mkdir, pattern_manager, sample_pattern):
        """カスタムパターン保存時の権限エラーテスト"""
        patterns = [sample_pattern]

        with pytest.raises(ConfigurationError) as exc_info:
            pattern_manager._save_all_custom_patterns(patterns)

        assert "カスタムパターンの保存に失敗しました" in str(exc_info.value)

    def test_patterns_conflict_same_category_common_keywords(self, pattern_manager, sample_pattern):
        """同じカテゴリで共通キーワードを持つパターンの競合テスト"""
        pattern2 = Pattern(
            id="test_pattern_002",
            name="別のパターン",
            category=sample_pattern.category,  # 同じカテゴリ
            regex_patterns=[r"warning:\s+(.+)"],
            keywords=["error", "warning"],  # 共通キーワード "error"
            context_requirements=[],
            confidence_base=0.7,
            success_rate=0.0,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            user_defined=True,
        )

        result = pattern_manager._patterns_conflict(sample_pattern, pattern2)

        assert result is True

    def test_patterns_conflict_different_category(self, pattern_manager, sample_pattern):
        """異なるカテゴリのパターンの競合テスト"""
        pattern2 = Pattern(
            id="test_pattern_002",
            name="別のパターン",
            category="different_category",  # 異なるカテゴリ
            regex_patterns=[r"warning:\s+(.+)"],
            keywords=["error", "warning"],  # 共通キーワードがあっても
            context_requirements=[],
            confidence_base=0.7,
            success_rate=0.0,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            user_defined=True,
        )

        result = pattern_manager._patterns_conflict(sample_pattern, pattern2)

        assert result is False

    def test_patterns_conflict_no_common_keywords(self, pattern_manager, sample_pattern):
        """共通キーワードがないパターンの競合テスト"""
        pattern2 = Pattern(
            id="test_pattern_002",
            name="別のパターン",
            category=sample_pattern.category,  # 同じカテゴリ
            regex_patterns=[r"warning:\s+(.+)"],
            keywords=["warning", "info"],  # 共通キーワードなし
            context_requirements=[],
            confidence_base=0.7,
            success_rate=0.0,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            user_defined=True,
        )

        result = pattern_manager._patterns_conflict(sample_pattern, pattern2)

        assert result is False
