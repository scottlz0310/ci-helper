"""
日本語エラーメッセージシステム

エラーメッセージとユーザー向けメッセージの日本語化を提供します。
"""

from __future__ import annotations


class JapaneseMessageProvider:
    """日本語メッセージプロバイダー"""

    def __init__(self):
        self.error_messages = self._load_error_messages()
        self.user_messages = self._load_user_messages()
        self.help_messages = self._load_help_messages()

    def _load_error_messages(self) -> dict[str, str]:
        """エラーメッセージを読み込み"""
        return {
            # AI関連エラー
            "api_key_error": "APIキーが設定されていません。環境変数 {env_var} を設定してください。",
            "api_key_invalid": "APIキーが無効です。{provider} のダッシュボードで確認してください。",
            "rate_limit_error": "レート制限に達しました。{retry_after}秒後に再試行してください。",
            "token_limit_error": "入力が長すぎます。トークン数を {limit} 以下に削減してください。",
            "network_error": "ネットワークエラーが発生しました。インターネット接続を確認してください。",
            "provider_error": "{provider} プロバイダーでエラーが発生しました: {details}",
            "configuration_error": "設定エラー: {config_key} の値が正しくありません。",
            "security_error": "セキュリティエラー: {details}",
            # ファイル関連エラー
            "file_not_found": "ファイルが見つかりません: {file_path}",
            "file_read_error": "ファイルの読み込みに失敗しました: {file_path} - {error}",
            "file_write_error": "ファイルの書き込みに失敗しました: {file_path} - {error}",
            "file_permission_error": "ファイルへのアクセス権限がありません: {file_path}",
            "directory_not_found": "ディレクトリが見つかりません: {directory_path}",
            "directory_create_error": "ディレクトリの作成に失敗しました: {directory_path}",
            # パターン認識エラー
            "pattern_load_error": "パターンの読み込みに失敗しました: {pattern_file}",
            "pattern_compile_error": "正規表現パターンのコンパイルに失敗しました: {pattern}",
            "pattern_match_error": "パターンマッチング中にエラーが発生しました: {error}",
            "pattern_database_error": "パターンデータベースエラー: {details}",
            # 自動修正エラー
            "fix_application_error": "修正の適用に失敗しました: {error}",
            "backup_creation_error": "バックアップの作成に失敗しました: {error}",
            "rollback_error": "ロールバックに失敗しました: {error}",
            "verification_error": "修正後の検証に失敗しました: {error}",
            # CI関連エラー
            "workflow_not_found": "ワークフローファイルが見つかりません。.github/workflows/ ディレクトリを確認してください。",
            "act_not_found": "act コマンドが見つかりません。インストールしてください。",
            "docker_not_found": "Docker が見つかりません。インストールしてください。",
            "docker_permission_error": "Docker への権限がありません。ユーザーを docker グループに追加してください。",
            "log_extraction_error": "ログの抽出に失敗しました: {error}",
            # 依存関係エラー
            "dependency_missing": "必要な依存関係が見つかりません: {dependency}",
            "dependency_version_error": "{dependency} のバージョンが古すぎます。{required_version} 以上が必要です。",
            "python_version_error": "Python のバージョンが古すぎます。{required_version} 以上が必要です。",
            # 設定エラー
            "config_file_not_found": "設定ファイルが見つかりません: {config_file}",
            "config_parse_error": "設定ファイルの解析に失敗しました: {error}",
            "config_validation_error": "設定の検証に失敗しました: {field} - {error}",
            "config_missing_section": "設定ファイルに必要なセクションがありません: {section}",
            # 一般的なエラー
            "unexpected_error": "予期しないエラーが発生しました: {error}",
            "timeout_error": "処理がタイムアウトしました。時間を置いて再試行してください。",
            "memory_error": "メモリ不足です。処理を分割するか、システムメモリを増やしてください。",
            "permission_denied": "権限が拒否されました: {operation}",
            "operation_cancelled": "操作がキャンセルされました。",
            "validation_error": "入力の検証に失敗しました: {details}",
        }

    def _load_user_messages(self) -> dict[str, str]:
        """ユーザー向けメッセージを読み込み"""
        return {
            # 成功メッセージ
            "analysis_completed": "分析が完了しました。",
            "fix_applied_successfully": "修正が正常に適用されました。",
            "backup_created": "バックアップが作成されました: {backup_id}",
            "rollback_completed": "ロールバックが完了しました。",
            "configuration_updated": "設定が更新されました。",
            "pattern_added": "新しいパターンが追加されました: {pattern_name}",
            # 進捗メッセージ
            "initializing": "初期化中...",
            "loading_patterns": "パターンを読み込み中...",
            "analyzing_log": "ログを分析中...",
            "generating_fixes": "修正提案を生成中...",
            "applying_fix": "修正を適用中...",
            "creating_backup": "バックアップを作成中...",
            "verifying_fix": "修正を検証中...",
            # 確認メッセージ
            "confirm_fix_application": "この修正を適用しますか？",
            "confirm_rollback": "ロールバックを実行しますか？",
            "confirm_overwrite": "既存のファイルを上書きしますか？",
            "confirm_delete": "このファイルを削除しますか？",
            # 警告メッセージ
            "high_risk_fix": "⚠️  この修正は高リスクです。慎重に検討してください。",
            "backup_recommended": "💡 修正前にバックアップを作成することをお勧めします。",
            "manual_verification_needed": "🔍 修正後に手動での検証が必要です。",
            "experimental_feature": "🧪 この機能は実験的です。注意して使用してください。",
            # 情報メッセージ
            "no_patterns_found": "マッチするパターンが見つかりませんでした。",
            "no_fixes_available": "利用可能な修正提案がありません。",
            "cache_hit": "キャッシュからの結果を使用しています。",
            "fallback_mode": "フォールバックモードで動作しています。",
            "learning_mode_active": "学習モードが有効です。",
            # ヘルプメッセージ
            "see_help": "詳細なヘルプは --help オプションを使用してください。",
            "see_documentation": "詳細なドキュメントは {url} を参照してください。",
            "report_issue": "問題が続く場合は GitHub Issues で報告してください: {url}",
            "check_environment": "環境設定を確認するには 'ci-run doctor' を実行してください。",
        }

    def _load_help_messages(self) -> dict[str, str]:
        """ヘルプメッセージを読み込み"""
        return {
            # コマンドヘルプ
            "analyze_help": "CI/CDの失敗ログをAIで分析し、根本原因の特定と修正提案を提供します。",
            "test_help": "GitHub Actionsワークフローをローカルで実行します。",
            "doctor_help": "システム環境と設定を診断します。",
            "init_help": "CI-Helperの初期設定を行います。",
            "logs_help": "ログファイルの管理と表示を行います。",
            "clean_help": "キャッシュファイルとログファイルをクリーンアップします。",
            # オプションヘルプ
            "provider_help": "使用するAIプロバイダーを指定します（openai/anthropic/local）。",
            "model_help": "使用するAIモデルを指定します（例: gpt-4o, claude-3-sonnet）。",
            "fix_help": "修正提案を生成し、適用の確認を行います。",
            "interactive_help": "対話的なAIデバッグモードを開始します。",
            "verbose_help": "詳細な実行情報を表示します。",
            "cache_help": "AIレスポンスキャッシュの使用を制御します。",
            # トラブルシューティングヘルプ
            "troubleshooting_steps": """
トラブルシューティング手順:
1. 環境診断を実行: ci-run doctor
2. 設定を確認: ci-helper.toml ファイルをチェック
3. APIキーを設定: 環境変数を確認
4. キャッシュをクリア: ci-run clean --cache-only
5. 詳細ログを確認: --verbose オプションを使用
            """,
            "common_issues": """
よくある問題と解決方法:

🔑 APIキーエラー:
   export OPENAI_API_KEY=your_key
   export ANTHROPIC_API_KEY=your_key

🌐 ネットワークエラー:
   - インターネット接続を確認
   - プロキシ設定を確認
   - ファイアウォール設定を確認

🐳 Docker権限エラー:
   sudo usermod -aG docker $USER
   newgrp docker

📦 依存関係エラー:
   - act をインストール
   - Docker をインストール
   - Python 3.8+ を使用
            """,
            "performance_tips": """
パフォーマンス改善のヒント:

⚡ 高速化:
   - キャッシュを有効にする (--cache)
   - 小さなモデルを使用 (--model gpt-4o-mini)
   - ログを圧縮 (--compress)

💾 メモリ節約:
   - チャンクサイズを小さくする
   - 並列処理数を減らす
   - 不要なキャッシュを削除

🎯 精度向上:
   - 適切なプロバイダーを選択
   - カスタムパターンを追加
   - フィードバックを提供
            """,
        }

    def get_error_message(self, error_key: str, **kwargs) -> str:
        """エラーメッセージを取得

        Args:
            error_key: エラーキー
            **kwargs: メッセージのフォーマット用パラメータ

        Returns:
            フォーマットされたエラーメッセージ
        """
        template = self.error_messages.get(error_key, f"不明なエラー: {error_key}")
        try:
            return template.format(**kwargs)
        except KeyError as e:
            return f"{template} (パラメータエラー: {e})"

    def get_user_message(self, message_key: str, **kwargs) -> str:
        """ユーザーメッセージを取得

        Args:
            message_key: メッセージキー
            **kwargs: メッセージのフォーマット用パラメータ

        Returns:
            フォーマットされたユーザーメッセージ
        """
        template = self.user_messages.get(message_key, f"不明なメッセージ: {message_key}")
        try:
            return template.format(**kwargs)
        except KeyError as e:
            return f"{template} (パラメータエラー: {e})"

    def get_help_message(self, help_key: str, **kwargs) -> str:
        """ヘルプメッセージを取得

        Args:
            help_key: ヘルプキー
            **kwargs: メッセージのフォーマット用パラメータ

        Returns:
            フォーマットされたヘルプメッセージ
        """
        template = self.help_messages.get(help_key, f"ヘルプが見つかりません: {help_key}")
        try:
            return template.format(**kwargs)
        except KeyError as e:
            return f"{template} (パラメータエラー: {e})"

    def format_exception_message(self, exception: Exception, context: str | None = None) -> str:
        """例外を日本語メッセージにフォーマット

        Args:
            exception: 例外オブジェクト
            context: 追加のコンテキスト情報

        Returns:
            日本語化された例外メッセージ
        """
        exception_type = type(exception).__name__
        exception_message = str(exception)

        # 例外タイプ別の日本語化
        type_translations = {
            "FileNotFoundError": "ファイルが見つかりません",
            "PermissionError": "権限エラー",
            "ConnectionError": "接続エラー",
            "TimeoutError": "タイムアウトエラー",
            "ValueError": "値エラー",
            "TypeError": "型エラー",
            "KeyError": "キーエラー",
            "AttributeError": "属性エラー",
            "ImportError": "インポートエラー",
            "ModuleNotFoundError": "モジュールが見つかりません",
            "SyntaxError": "構文エラー",
            "IndentationError": "インデントエラー",
            "NameError": "名前エラー",
            "IndexError": "インデックスエラー",
            "KeyboardInterrupt": "キーボード割り込み",
            "SystemExit": "システム終了",
            "RuntimeError": "実行時エラー",
            "OSError": "OS エラー",
            "IOError": "入出力エラー",
            "MemoryError": "メモリエラー",
        }

        japanese_type = type_translations.get(exception_type, exception_type)

        # コンテキスト情報を追加
        if context:
            return f"{japanese_type}: {exception_message} (コンテキスト: {context})"
        else:
            return f"{japanese_type}: {exception_message}"

    def get_suggestion_for_error(self, error_key: str) -> str | None:
        """エラーに対する解決提案を取得

        Args:
            error_key: エラーキー

        Returns:
            解決提案（存在する場合）
        """
        suggestions = {
            "api_key_error": "APIキーを環境変数に設定するか、設定ファイルで指定してください。",
            "rate_limit_error": "しばらく待ってから再試行するか、より小さなモデルを使用してください。",
            "token_limit_error": "入力を短縮するか、より大きなコンテキストウィンドウを持つモデルを使用してください。",
            "network_error": "インターネット接続を確認し、プロキシ設定を見直してください。",
            "file_not_found": "ファイルパスを確認し、ファイルが存在することを確認してください。",
            "docker_permission_error": "ユーザーを docker グループに追加するか、sudo で実行してください。",
            "workflow_not_found": "GitHub Actions ワークフローファイルを .github/workflows/ に作成してください。",
            "config_file_not_found": "'ci-run init' コマンドで設定ファイルを作成してください。",
        }

        return suggestions.get(error_key)

    def get_recovery_steps(self, error_key: str) -> List[str]:
        """エラーからの復旧手順を取得

        Args:
            error_key: エラーキー

        Returns:
            復旧手順のリスト
        """
        recovery_steps = {
            "api_key_error": [
                "APIキーを取得する",
                "環境変数に設定する",
                "設定ファイルを更新する",
                "コマンドを再実行する",
            ],
            "network_error": [
                "インターネット接続を確認する",
                "プロキシ設定を確認する",
                "ファイアウォール設定を確認する",
                "DNS設定を確認する",
                "しばらく待ってから再試行する",
            ],
            "docker_permission_error": [
                "Docker グループにユーザーを追加する",
                "ログアウト・ログインする",
                "Docker サービスを再起動する",
                "権限を確認する",
            ],
            "configuration_error": [
                "設定ファイルを確認する",
                "環境変数を確認する",
                "'ci-run doctor' で診断する",
                "'ci-run init' で設定を再生成する",
            ],
        }

        return recovery_steps.get(
            error_key,
            [
                "エラーメッセージを確認する",
                "'ci-run doctor' で環境を診断する",
                "詳細ログを確認する (--verbose)",
                "GitHub Issues で報告する",
            ],
        )


# グローバルインスタンス
_japanese_messages = JapaneseMessageProvider()


def get_japanese_message(message_type: str, key: str, **kwargs) -> str:
    """日本語メッセージを取得

    Args:
        message_type: メッセージタイプ（error/user/help）
        key: メッセージキー
        **kwargs: フォーマット用パラメータ

    Returns:
        日本語メッセージ
    """
    if message_type == "error":
        return _japanese_messages.get_error_message(key, **kwargs)
    elif message_type == "user":
        return _japanese_messages.get_user_message(key, **kwargs)
    elif message_type == "help":
        return _japanese_messages.get_help_message(key, **kwargs)
    else:
        return f"不明なメッセージタイプ: {message_type}"


def format_japanese_exception(exception: Exception, context: str | None = None) -> str:
    """例外を日本語でフォーマット

    Args:
        exception: 例外オブジェクト
        context: コンテキスト情報

    Returns:
        日本語化された例外メッセージ
    """
    return _japanese_messages.format_exception_message(exception, context)


def get_error_suggestion(error_key: str) -> str | None:
    """エラーの解決提案を取得

    Args:
        error_key: エラーキー

    Returns:
        解決提案
    """
    return _japanese_messages.get_suggestion_for_error(error_key)


def get_recovery_steps(error_key: str) -> List[str]:
    """復旧手順を取得

    Args:
        error_key: エラーキー

    Returns:
        復旧手順のリスト
    """
    return _japanese_messages.get_recovery_steps(error_key)


class JapaneseErrorHandler:
    """日本語エラーハンドラー"""

    def __init__(self):
        self.messages = _japanese_messages

    def handle_error(self, error: Exception, context: str | None = None) -> dict[str, str]:
        """エラーを処理して日本語メッセージを生成

        Args:
            error: 例外オブジェクト
            context: コンテキスト情報

        Returns:
            エラー情報の辞書
        """
        error_type = type(error).__name__
        error_message = self.messages.format_exception_message(error, context)

        # エラータイプからキーを推測
        error_key = self._infer_error_key(error)
        suggestion = self.messages.get_suggestion_for_error(error_key)
        recovery_steps = self.messages.get_recovery_steps(error_key)

        return {
            "type": error_type,
            "message": error_message,
            "suggestion": suggestion,
            "recovery_steps": recovery_steps,
            "context": context,
        }

    def _infer_error_key(self, error: Exception) -> str:
        """例外からエラーキーを推測

        Args:
            error: 例外オブジェクト

        Returns:
            推測されたエラーキー
        """
        error_type = type(error).__name__
        error_message = str(error).lower()

        # エラーメッセージの内容から推測
        if "api key" in error_message or "authentication" in error_message:
            return "api_key_error"
        elif "rate limit" in error_message or "quota" in error_message:
            return "rate_limit_error"
        elif "token" in error_message and "limit" in error_message:
            return "token_limit_error"
        elif "network" in error_message or "connection" in error_message:
            return "network_error"
        elif "docker" in error_message and "permission" in error_message:
            return "docker_permission_error"
        elif "workflow" in error_message or ".github" in error_message:
            return "workflow_not_found"
        elif "config" in error_message:
            return "configuration_error"
        elif error_type == "FileNotFoundError":
            return "file_not_found"
        elif error_type == "PermissionError":
            return "permission_denied"
        else:
            return "unexpected_error"
