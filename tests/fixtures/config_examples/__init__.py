"""
設定例ディレクトリ

テスト用の設定ファイル例を提供します。

利用可能な設定ファイル:

TOML設定ファイル:
- basic_ci_helper.toml: 基本的なCI-Helper設定
- ai_enabled_ci_helper.toml: AI機能を有効にした設定
- minimal_ci_helper.toml: 最小限の設定
- multi_provider_ci_helper.toml: 複数プロバイダー対応設定
- invalid_ci_helper.toml: 無効な設定（エラーテスト用）
- pattern_recognition_ci_helper.toml: パターン認識機能有効設定
- auto_fix_ci_helper.toml: 自動修正機能有効設定
- learning_enabled_ci_helper.toml: 学習機能有効設定

JSON設定ファイル:
- ai_config.json: AI設定のJSON形式
- test_config.json: テスト用設定
- performance_test_config.json: パフォーマンステスト用設定
- error_configs.json: エラーテスト用設定

環境変数ファイル:
- .env.example: 環境変数設定例
- .env.test: テスト用環境変数

Act設定ファイル:
- .actrc.example: Act設定例
- .actrc.basic: 基本的なAct設定
- .actrc.privileged: 権限付きAct設定

使用方法:
    from tests.fixtures.config_loader import load_toml_config, load_json_config

    # TOML設定を読み込み
    config = load_toml_config("basic_ci_helper.toml")

    # JSON設定を読み込み
    ai_config = load_json_config("ai_config.json")
"""
