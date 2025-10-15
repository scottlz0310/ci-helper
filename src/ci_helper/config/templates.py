"""
設定ファイルテンプレート

initコマンドで生成される設定ファイルのテンプレートを定義します。
"""

# .actrc テンプレート
ACTRC_TEMPLATE = """-P ubuntu-latest=ghcr.io/catthehacker/ubuntu:full-24.04
-P ubuntu-22.04=ghcr.io/catthehacker/ubuntu:full-22.04
-P ubuntu-20.04=ghcr.io/catthehacker/ubuntu:full-20.04
--container-daemon-socket -
"""

# ci-helper.toml テンプレート
CI_HELPER_TOML_TEMPLATE = """# ci-helper 設定ファイル
# 詳細な設定オプションについては、ドキュメントを参照してください

[ci-helper]
# ログとキャッシュディレクトリ
log_dir = ".ci-helper/logs"
cache_dir = ".ci-helper/cache"
reports_dir = ".ci-helper/reports"

# ログ解析設定
context_lines = 3  # エラー前後のコンテキスト行数
max_log_size_mb = 100  # 最大ログファイルサイズ（MB）
max_cache_size_mb = 500  # 最大キャッシュサイズ（MB）

# act実行設定
act_image = "ghcr.io/catthehacker/ubuntu:full-24.04"  # デフォルトDockerイメージ
timeout_seconds = 1800  # タイムアウト（秒）

# デフォルト動作
verbose = false  # 詳細ログを有効にするか
save_logs = true  # ログを自動保存するか

# AI統合設定（フェーズ3で使用）
# [ci-helper.ai]
# provider = "openai"  # AI プロバイダー
# model = "gpt-4"  # 使用するモデル
# max_tokens = 4000  # 最大トークン数
"""

# .env.example テンプレート
ENV_EXAMPLE_TEMPLATE = """# ci-helper 環境変数設定例
# このファイルを .env にコピーして使用してください

# 基本設定（ci-helper.tomlの設定を上書き）
# CI_HELPER_VERBOSE=false
# CI_HELPER_SAVE_LOGS=true
# CI_HELPER_TIMEOUT_SECONDS=1800

# act実行設定
# CI_HELPER_ACT_IMAGE=ghcr.io/catthehacker/ubuntu:full-24.04

# ログ設定
# CI_HELPER_LOG_DIR=.ci-helper/logs
# CI_HELPER_CACHE_DIR=.ci-helper/cache
# CI_HELPER_MAX_LOG_SIZE_MB=100

# AI統合設定（フェーズ3で使用）
# OPENAI_API_KEY=your_openai_api_key_here
# ANTHROPIC_API_KEY=your_anthropic_api_key_here
# GOOGLE_API_KEY=your_google_api_key_here

# GitHub設定（必要に応じて）
# GITHUB_TOKEN=your_github_token_here
"""

# .gitignore に追加する内容
GITIGNORE_ADDITIONS = """
# ci-helper
.ci-helper/
ci-helper.toml
.env
"""
