"""
AIプロバイダーのテスト

各AIプロバイダー（OpenAI、Anthropic、ローカルLLM）の機能をテストします。
"""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.ci_helper.ai.exceptions import APIKeyError, ProviderError, RateLimitError
from src.ci_helper.ai.models import AnalysisResult, AnalyzeOptions, ProviderConfig
from src.ci_helper.ai.providers.anthropic import AnthropicProvider
from src.ci_helper.ai.providers.local import LocalLLMProvider
from src.ci_helper.ai.providers.openai import OpenAIProvider


class TestAIProviderBase:
    """AIProvider基底クラスのテスト"""

    def test_provider_initialization(self):
        """プロバイダー初期化のテスト"""
        config = ProviderConfig(
            name="test",
            api_key="test-key",
            base_url="https://api.test.com",
            default_model="test-model",
            available_models=["test-model"],
            timeout_seconds=30,
            max_retries=3,
        )

        # 抽象クラスなので直接インスタンス化はできないが、設定は確認できる
        assert config.name == "test"
        assert config.api_key == "test-key"
        assert config.default_model == "test-model"


class TestOpenAIProvider:
    """OpenAIプロバイダーのテスト"""

    @pytest.fixture
    def openai_config(self):
        """OpenAI設定"""
        return ProviderConfig(
            name="openai",
            api_key="sk-test-key-123",
            base_url="https://api.openai.com/v1",
            default_model="gpt-4o",
            available_models=["gpt-4o", "gpt-4o-mini"],
            timeout_seconds=30,
            max_retries=3,
        )

    @pytest.fixture
    def openai_provider(self, openai_config):
        """OpenAIプロバイダー"""
        return OpenAIProvider(openai_config)

    @pytest.fixture
    def analyze_options(self):
        """分析オプション"""
        return AnalyzeOptions(
            provider="openai",
            model="gpt-4o",
            use_cache=True,
            streaming=False,
            custom_prompt=None,
        )

    def test_openai_provider_initialization(self, openai_provider):
        """OpenAIプロバイダー初期化のテスト"""
        assert openai_provider.name == "openai"
        assert openai_provider.config.api_key == "sk-test-key-123"
        assert openai_provider.config.default_model == "gpt-4o"

    def test_model_limits(self, openai_provider):
        """モデル制限のテスト"""
        assert OpenAIProvider.MODEL_LIMITS["gpt-4o"] == 128000
        assert OpenAIProvider.MODEL_LIMITS["gpt-4o-mini"] == 128000
        assert OpenAIProvider.MODEL_LIMITS["gpt-4"] == 8192

    def test_model_costs(self, openai_provider):
        """モデルコストのテスト"""
        gpt4o_cost = OpenAIProvider.MODEL_COSTS["gpt-4o"]
        assert gpt4o_cost["input"] == 0.0025
        assert gpt4o_cost["output"] == 0.01

        gpt4o_mini_cost = OpenAIProvider.MODEL_COSTS["gpt-4o-mini"]
        assert gpt4o_mini_cost["input"] == 0.00015
        assert gpt4o_mini_cost["output"] == 0.0006

    def test_estimate_cost(self, openai_provider):
        """コスト推定のテスト"""
        # gpt-4oで1000入力トークン、500出力トークンの場合
        cost = openai_provider.estimate_cost(1000, 500, "gpt-4o")
        expected = (1000 * 0.0025 / 1000) + (500 * 0.01 / 1000)  # 0.0025 + 0.005 = 0.0075
        assert cost == expected

    def test_get_available_models(self, openai_provider):
        """利用可能モデル取得のテスト"""
        models = openai_provider.get_available_models()
        assert "gpt-4o" in models
        assert "gpt-4o-mini" in models

    def test_validate_model(self, openai_provider):
        """モデル検証のテスト"""
        # 有効なモデル
        assert openai_provider.validate_model("gpt-4o") is True
        assert openai_provider.validate_model("gpt-4o-mini") is True

        # 無効なモデル
        assert openai_provider.validate_model("invalid-model") is False

    @pytest.mark.asyncio
    async def test_initialize_success(self, openai_provider):
        """初期化成功のテスト"""
        # 初期状態では_clientはNone
        assert openai_provider._client is None

        with patch("src.ci_helper.ai.providers.openai.AsyncOpenAI") as mock_openai:
            mock_client = Mock()
            mock_openai.return_value = mock_client

            # validate_connectionをモック
            with patch.object(openai_provider, "validate_connection", return_value=True) as mock_validate:
                await openai_provider.initialize()

                assert openai_provider._client is not None
                mock_openai.assert_called_once_with(
                    api_key="sk-test-key-123",
                    timeout=30,
                    max_retries=3,
                )
                mock_validate.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_invalid_api_key(self, openai_config):
        """無効なAPIキーでの初期化テスト"""
        openai_config.api_key = "invalid-key"
        provider = OpenAIProvider(openai_config)

        with patch("openai.AsyncOpenAI") as mock_openai:
            mock_client = Mock()
            mock_openai.return_value = mock_client

            # validate_connectionでAPIKeyErrorを発生させる
            with patch.object(provider, "validate_connection", side_effect=APIKeyError("openai", "Invalid API key")):
                with pytest.raises(APIKeyError):  # APIKeyErrorはそのまま再発生される
                    await provider.initialize()

    @pytest.mark.asyncio
    async def test_analyze_success(self, openai_provider, analyze_options):
        """分析成功のテスト"""
        # モックレスポンス
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "分析結果: テストが失敗しました"
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50

        with patch("openai.AsyncOpenAI") as mock_openai:
            mock_client = Mock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai.return_value = mock_client
            openai_provider._client = mock_client

            result = await openai_provider.analyze("分析してください", "ログ内容", analyze_options)

            assert isinstance(result, AnalysisResult)
            assert result.summary == "分析結果: テストが失敗しました"
            assert result.tokens_used.input_tokens == 100
            assert result.tokens_used.output_tokens == 50

    @pytest.mark.asyncio
    async def test_analyze_rate_limit_error(self, openai_provider, analyze_options):
        """レート制限エラーのテスト"""
        import openai

        with patch("openai.AsyncOpenAI") as mock_openai:
            mock_client = Mock()
            rate_limit_error = openai.RateLimitError(
                message="Rate limit exceeded",
                response=Mock(),
                body=None,
            )
            mock_client.chat.completions.create = AsyncMock(side_effect=rate_limit_error)
            mock_openai.return_value = mock_client
            openai_provider._client = mock_client

            with pytest.raises(RateLimitError):
                await openai_provider.analyze("分析してください", "ログ内容", analyze_options)

    @pytest.mark.asyncio
    async def test_stream_analyze(self, openai_provider, analyze_options):
        """ストリーミング分析のテスト"""

        # モックストリームレスポンス
        async def mock_stream():
            chunks = [
                Mock(choices=[Mock(delta=Mock(content="分析"))]),
                Mock(choices=[Mock(delta=Mock(content="結果"))]),
                Mock(choices=[Mock(delta=Mock(content="です"))]),
            ]
            for chunk in chunks:
                yield chunk

        with patch("openai.AsyncOpenAI") as mock_openai:
            mock_client = Mock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())
            mock_openai.return_value = mock_client
            openai_provider._client = mock_client

            analyze_options.stream = True
            chunks = []
            async for chunk in openai_provider.stream_analyze("分析してください", "ログ内容", analyze_options):
                chunks.append(chunk)

            assert len(chunks) == 3
            assert chunks == ["分析", "結果", "です"]


class TestAnthropicProvider:
    """Anthropicプロバイダーのテスト"""

    @pytest.fixture
    def anthropic_config(self):
        """Anthropic設定"""
        return ProviderConfig(
            name="anthropic",
            api_key="sk-ant-test-key-123",
            base_url="https://api.anthropic.com",
            default_model="claude-3-5-sonnet-20241022",
            available_models=["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"],
            timeout_seconds=30,
            max_retries=3,
        )

    @pytest.fixture
    def anthropic_provider(self, anthropic_config):
        """Anthropicプロバイダー"""
        return AnthropicProvider(anthropic_config)

    def test_anthropic_provider_initialization(self, anthropic_provider):
        """Anthropicプロバイダー初期化のテスト"""
        assert anthropic_provider.name == "anthropic"
        assert anthropic_provider.config.api_key == "sk-ant-test-key-123"
        assert anthropic_provider.config.default_model == "claude-3-5-sonnet-20241022"

    def test_model_costs(self, anthropic_provider):
        """モデルコストのテスト"""
        sonnet_cost = AnthropicProvider.MODEL_COSTS["claude-3-5-sonnet-20241022"]
        assert sonnet_cost["input"] == 0.003
        assert sonnet_cost["output"] == 0.015

        haiku_cost = AnthropicProvider.MODEL_COSTS["claude-3-5-haiku-20241022"]
        assert haiku_cost["input"] == 0.00025
        assert haiku_cost["output"] == 0.00125

    @pytest.mark.asyncio
    async def test_initialize_success(self, anthropic_provider):
        """初期化成功のテスト"""
        with patch("src.ci_helper.ai.providers.anthropic.AsyncAnthropic") as mock_anthropic:
            mock_client = Mock()
            mock_anthropic.return_value = mock_client

            # validate_connectionをモック
            with patch.object(anthropic_provider, "validate_connection", return_value=True) as mock_validate:
                await anthropic_provider.initialize()

                assert anthropic_provider._client is not None
                mock_anthropic.assert_called_once_with(
                    api_key="sk-ant-test-key-123",
                    timeout=30,
                    max_retries=3,
                )
                mock_validate.assert_called_once()


class TestLocalLLMProvider:
    """ローカルLLMプロバイダーのテスト"""

    @pytest.fixture
    def local_config(self):
        """ローカルLLM設定"""
        return ProviderConfig(
            name="local",
            api_key="",  # ローカルLLMはAPIキー不要
            base_url="http://localhost:11434",
            default_model="llama3.2",
            available_models=["llama3.2", "codellama"],
            timeout_seconds=60,
            max_retries=2,
        )

    @pytest.fixture
    def local_provider(self, local_config):
        """ローカルLLMプロバイダー"""
        return LocalLLMProvider(local_config)

    def test_local_provider_initialization(self, local_provider):
        """ローカルLLMプロバイダー初期化のテスト"""
        assert local_provider.name == "local"
        assert local_provider.config.base_url == "http://localhost:11434"
        assert local_provider.config.default_model == "llama3.2"

    @pytest.mark.asyncio
    async def test_validate_connection_success(self, local_provider):
        """Ollama接続確認成功のテスト"""
        # セッションを初期化
        local_provider._session = Mock()

        with patch.object(local_provider._session, "get") as mock_get:
            mock_response = Mock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"models": [{"name": "llama3.2"}]})
            mock_get.return_value.__aenter__.return_value = mock_response

            result = await local_provider.validate_connection()
            assert result is True

    @pytest.mark.asyncio
    async def test_validate_connection_failure(self, local_provider):
        """Ollama接続確認失敗のテスト"""
        # セッションを初期化
        local_provider._session = Mock()

        with patch.object(local_provider._session, "get") as mock_get:
            mock_get.side_effect = Exception("Connection failed")

            with pytest.raises(ProviderError):
                await local_provider.validate_connection()

    def test_estimate_cost_always_zero(self, local_provider):
        """ローカルLLMのコスト推定（常に0）のテスト"""
        cost = local_provider.estimate_cost("llama3.2", 1000, 500)
        assert cost == 0.0

    @pytest.mark.asyncio
    async def test_initialize_success(self, local_provider):
        """初期化成功のテスト"""
        with patch.object(local_provider, "validate_connection", return_value=True):
            with patch("aiohttp.ClientSession") as mock_session_class:
                mock_session = Mock()
                mock_session_class.return_value = mock_session

                await local_provider.initialize()
                # 例外が発生しないことを確認
                assert local_provider._session is not None

    @pytest.mark.asyncio
    async def test_initialize_connection_failure(self, local_provider):
        """接続失敗時の初期化テスト"""
        # 非同期モックセッションを作成
        mock_session = AsyncMock()
        mock_session.close = AsyncMock()

        with patch.object(
            local_provider, "validate_connection", side_effect=ProviderError("local", "Connection failed")
        ):
            with patch("aiohttp.ClientSession", return_value=mock_session):
                with pytest.raises(ProviderError):
                    await local_provider.initialize()

                # セッションのクローズが呼ばれたことを確認
                mock_session.close.assert_called_once()


class TestTemplateLoader:
    """テンプレートローダーのテスト"""

    @pytest.fixture
    def temp_template_dir(self, tmp_path):
        """一時テンプレートディレクトリ"""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        return template_dir

    @pytest.fixture
    def template_loader(self, temp_template_dir):
        """テンプレートローダー"""
        from src.ci_helper.ai.template_loader import TemplateLoader

        return TemplateLoader(temp_template_dir)

    def test_template_loader_initialization(self, template_loader, temp_template_dir):
        """テンプレートローダー初期化のテスト"""
        assert template_loader.template_dir == temp_template_dir

    def test_template_loader_default_dir(self):
        """デフォルトディレクトリでの初期化テスト"""
        from src.ci_helper.ai.template_loader import TemplateLoader

        loader = TemplateLoader()
        assert loader.template_dir == Path("templates")

    def test_load_template_file_success(self, template_loader, temp_template_dir):
        """テンプレートファイル読み込み成功のテスト"""
        # テンプレートファイルを作成
        template_file = temp_template_dir / "test_template.txt"
        template_content = "これはテストテンプレートです。\n変数: {variable}"
        template_file.write_text(template_content, encoding="utf-8")

        # テンプレートを読み込み
        result = template_loader.load_template_file("test_template")
        assert result == template_content

    def test_load_template_file_not_found(self, template_loader):
        """存在しないテンプレートファイルの読み込みテスト"""
        from src.ci_helper.ai.exceptions import ConfigurationError

        with pytest.raises(ConfigurationError) as exc_info:
            template_loader.load_template_file("nonexistent")

        assert "テンプレートファイルが見つかりません" in str(exc_info.value)

    def test_load_template_file_read_error(self, template_loader, temp_template_dir):
        """テンプレートファイル読み込みエラーのテスト"""
        from src.ci_helper.ai.exceptions import ConfigurationError

        # 読み込み不可能なファイルを作成（権限エラーをシミュレート）
        template_file = temp_template_dir / "unreadable.txt"
        template_file.write_text("content", encoding="utf-8")

        # ファイル読み込みでエラーが発生するようにモック
        with patch("builtins.open", side_effect=PermissionError("Permission denied")):
            with pytest.raises(ConfigurationError) as exc_info:
                template_loader.load_template_file("unreadable")

            assert "テンプレートファイルの読み込みに失敗しました" in str(exc_info.value)

    def test_load_templates_from_config_success(self, template_loader, temp_template_dir):
        """設定ファイルからのテンプレート読み込み成功テスト"""
        # 設定ファイルを作成
        config_file = temp_template_dir / "config.toml"
        config_content = f"""
[ai.prompt_templates]
analysis = "{temp_template_dir / "analysis_template.txt"}"
fix = "{temp_template_dir / "fix_template.txt"}"
"""
        config_file.write_text(config_content, encoding="utf-8")

        # テンプレートファイルを作成（config.tomlと同じディレクトリに）
        (temp_template_dir / "analysis_template.txt").write_text("分析テンプレート", encoding="utf-8")
        (temp_template_dir / "fix_template.txt").write_text("修正テンプレート", encoding="utf-8")

        # テンプレートを読み込み
        templates = template_loader.load_templates_from_config(config_file)

        assert templates["analysis"] == "分析テンプレート"
        assert templates["fix"] == "修正テンプレート"

    def test_load_templates_from_config_file_not_found(self, template_loader, temp_template_dir):
        """存在しない設定ファイルからの読み込みテスト"""
        from src.ci_helper.ai.exceptions import ConfigurationError

        nonexistent_config = temp_template_dir / "nonexistent.toml"

        with pytest.raises(ConfigurationError) as exc_info:
            template_loader.load_templates_from_config(nonexistent_config)

        assert "設定ファイルが見つかりません" in str(exc_info.value)

    def test_load_templates_from_config_invalid_toml(self, template_loader, temp_template_dir):
        """無効なTOMLファイルからの読み込みテスト"""
        from src.ci_helper.ai.exceptions import ConfigurationError

        # 無効なTOMLファイルを作成
        config_file = temp_template_dir / "invalid.toml"
        config_file.write_text("invalid toml content [", encoding="utf-8")

        with pytest.raises(ConfigurationError) as exc_info:
            template_loader.load_templates_from_config(config_file)

        assert "設定ファイルからのテンプレート読み込みに失敗しました" in str(exc_info.value)

    def test_load_templates_from_config_missing_template_file(self, template_loader, temp_template_dir):
        """設定ファイルで指定されたテンプレートファイルが存在しない場合のテスト"""

        # 設定ファイルを作成（存在しないテンプレートファイルを指定）
        config_file = temp_template_dir / "config.toml"
        config_content = """
[ai.prompt_templates]
analysis = "missing_template.txt"
"""
        config_file.write_text(config_content, encoding="utf-8")

        # 存在しないファイルは単純にスキップされる（エラーにならない）
        templates = template_loader.load_templates_from_config(config_file)
        assert templates == {}  # 空の辞書が返される

    def test_load_templates_from_config_no_templates_section(self, template_loader, temp_template_dir):
        """templatesセクションがない設定ファイルのテスト"""
        # templatesセクションがない設定ファイルを作成
        config_file = temp_template_dir / "config.toml"
        config_content = """
[other_section]
key = "value"
"""
        config_file.write_text(config_content, encoding="utf-8")

        # templatesセクションがない場合は空の辞書を返す
        templates = template_loader.load_templates_from_config(config_file)
        assert templates == {}

    def test_save_template_success(self, template_loader, temp_template_dir):
        """テンプレート保存成功のテスト"""
        template_name = "new_template"
        template_content = "新しいテンプレート内容\n変数: {var}"

        template_loader.save_template(template_name, template_content)

        # ファイルが作成されたことを確認
        template_file = temp_template_dir / f"{template_name}.txt"
        assert template_file.exists()
        assert template_file.read_text(encoding="utf-8") == template_content

    def test_save_template_create_directory(self, tmp_path):
        """ディレクトリが存在しない場合の保存テスト"""
        from src.ci_helper.ai.template_loader import TemplateLoader

        # 存在しないディレクトリを指定
        nonexistent_dir = tmp_path / "nonexistent" / "templates"
        loader = TemplateLoader(nonexistent_dir)

        template_name = "test"
        template_content = "テスト内容"

        loader.save_template(template_name, template_content)

        # ディレクトリとファイルが作成されたことを確認
        assert nonexistent_dir.exists()
        template_file = nonexistent_dir / f"{template_name}.txt"
        assert template_file.exists()
        assert template_file.read_text(encoding="utf-8") == template_content

    def test_save_template_write_error(self, template_loader):
        """テンプレート保存エラーのテスト"""
        from src.ci_helper.ai.exceptions import ConfigurationError

        # ファイル書き込みでエラーが発生するようにモック
        with patch("builtins.open", side_effect=PermissionError("Permission denied")):
            with pytest.raises(ConfigurationError) as exc_info:
                template_loader.save_template("test", "content")

            assert "テンプレートの保存に失敗しました" in str(exc_info.value)

    def test_list_available_templates(self, template_loader, temp_template_dir):
        """利用可能なテンプレート一覧取得のテスト"""
        # テンプレートファイルを作成
        (temp_template_dir / "template1.txt").write_text("内容1", encoding="utf-8")
        (temp_template_dir / "template2.txt").write_text("内容2", encoding="utf-8")
        (temp_template_dir / "not_template.md").write_text("マークダウン", encoding="utf-8")  # .txtでないファイル

        templates = template_loader.list_available_templates()

        assert sorted(templates) == ["template1", "template2"]
        assert "not_template" not in templates  # .txtでないファイルは含まれない

    def test_list_available_templates_empty_directory(self, template_loader):
        """空のディレクトリでのテンプレート一覧取得テスト"""
        templates = template_loader.list_available_templates()
        assert templates == []

    def test_list_available_templates_nonexistent_directory(self, tmp_path):
        """存在しないディレクトリでのテンプレート一覧取得テスト"""
        from src.ci_helper.ai.template_loader import TemplateLoader

        nonexistent_dir = tmp_path / "nonexistent"
        loader = TemplateLoader(nonexistent_dir)

        templates = loader.list_available_templates()
        assert templates == []

    def test_template_exists_true(self, template_loader, temp_template_dir):
        """テンプレート存在確認（存在する場合）のテスト"""
        # テンプレートファイルを作成
        (temp_template_dir / "existing.txt").write_text("内容", encoding="utf-8")

        assert template_loader.template_exists("existing") is True

    def test_template_exists_false(self, template_loader):
        """テンプレート存在確認（存在しない場合）のテスト"""
        assert template_loader.template_exists("nonexistent") is False

    def test_get_template_info_success(self, template_loader, temp_template_dir):
        """テンプレート情報取得成功のテスト"""
        # テンプレートファイルを作成
        template_content = "テンプレート内容\n変数: {variable1}\n別の変数: {variable2}"
        template_file = temp_template_dir / "info_test.txt"
        template_file.write_text(template_content, encoding="utf-8")

        info = template_loader.get_template_info("info_test")

        assert info["name"] == "info_test"
        assert info["path"] == str(template_file)
        assert info["size"] > 0
        assert info["modified"] > 0
        assert info["lines"] == 3
        assert sorted(info["variables"]) == ["variable1", "variable2"]

    def test_get_template_info_not_found(self, template_loader):
        """存在しないテンプレートの情報取得テスト"""
        from src.ci_helper.ai.exceptions import ConfigurationError

        with pytest.raises(ConfigurationError) as exc_info:
            template_loader.get_template_info("nonexistent")

        assert "テンプレートが見つかりません" in str(exc_info.value)

    def test_get_template_info_error(self, template_loader, temp_template_dir):
        """テンプレート情報取得エラーのテスト"""
        from src.ci_helper.ai.exceptions import ConfigurationError

        # テンプレートファイルを作成
        template_file = temp_template_dir / "error_test.txt"
        template_file.write_text("内容", encoding="utf-8")

        # load_template_fileでエラーが発生するようにモック
        with patch.object(template_loader, "load_template_file", side_effect=OSError("File read error")):
            with pytest.raises(ConfigurationError) as exc_info:
                template_loader.get_template_info("error_test")

            assert "テンプレート情報の取得に失敗しました" in str(exc_info.value)

    def test_extract_variables(self, template_loader):
        """変数抽出のテスト"""
        content = """
        これは{variable1}のテストです。
        {variable2}と{variable1}が含まれています。
        {variable3}も含まれています。
        通常のテキストです。
        """

        variables = template_loader._extract_variables(content)
        assert sorted(variables) == ["variable1", "variable2", "variable3"]

    def test_extract_variables_no_variables(self, template_loader):
        """変数が含まれていないテンプレートの変数抽出テスト"""
        content = "これは変数が含まれていないテンプレートです。"

        variables = template_loader._extract_variables(content)
        assert variables == []

    def test_create_sample_templates(self, template_loader, temp_template_dir):
        """サンプルテンプレート作成のテスト"""
        template_loader.create_sample_templates()

        # サンプルテンプレートが作成されたことを確認
        assert (temp_template_dir / "custom_analysis.txt").exists()
        assert (temp_template_dir / "custom_fix.txt").exists()

        # 内容を確認
        analysis_content = (temp_template_dir / "custom_analysis.txt").read_text(encoding="utf-8")
        assert "{context}" in analysis_content
        assert "分析対象" in analysis_content

        fix_content = (temp_template_dir / "custom_fix.txt").read_text(encoding="utf-8")
        assert "{analysis_result}" in fix_content
        assert "修正提案" in fix_content

    def test_create_sample_templates_error(self, template_loader):
        """サンプルテンプレート作成エラーのテスト"""
        from src.ci_helper.ai.exceptions import ConfigurationError

        # save_templateでエラーが発生するようにモック
        with patch.object(template_loader, "save_template", side_effect=ConfigurationError("Save error")):
            with pytest.raises(ConfigurationError):
                template_loader.create_sample_templates()
