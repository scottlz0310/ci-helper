"""
init コマンド実装

設定ファイルテンプレートを生成します。
"""

from pathlib import Path

import click
from rich.console import Console
from rich.prompt import Confirm

from ..config.templates import ACTRC_TEMPLATE, CI_HELPER_TOML_TEMPLATE, ENV_EXAMPLE_TEMPLATE, GITIGNORE_ADDITIONS
from ..core.exceptions import ConfigurationError

console = Console()


SAMPLE_WORKFLOW_TEMPLATE = """name: CI Helper Sample
on:
  push:
    branches:
      - main
  pull_request:
    branches:
      - main

jobs:
  sample:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run sample task
        run: echo \"ci-helper sample workflow\"
"""


@click.command()
@click.option(
    "--force",
    is_flag=True,
    help="既存の設定ファイルを強制的に上書きします",
)
def init(force: bool) -> None:
    """プロジェクトの初期化

    ci-helper の設定ファイルを作成し、プロジェクトを初期化します。
    環境に依存しない汎用的な設定を生成します。

    \b
    生成されるファイル:
    - .actrc: act の設定ファイル（Git除外）
    - ci-helper.toml: ci-helper の設定ファイル（Git除外）
    - .env: 環境変数ファイル（Git除外）
    - .actrc.example, ci-helper.toml.example, .env.example: 参考用テンプレート（Git管理）

    \b
    注意:
    実際の設定ファイルは環境固有のため Git 除外されます。
    .example ファイルをチーム共有の参考として使用してください。
    """
    try:
        project_root = Path.cwd()

        console.print("[bold blue]🚀 プロジェクトを初期化しています...[/bold blue]\n")

        # 実際の設定ファイルの定義
        config_files = [
            (".actrc", "act の設定ファイル"),
            ("ci-helper.toml", "ci-helper の設定ファイル"),
            (".env", "環境変数ファイル"),
        ]

        # 既存の設定ファイルをチェック
        existing_config_files = []
        for filename, _ in config_files:
            file_path = project_root / filename
            if file_path.exists():
                existing_config_files.append(filename)

        # 既存の設定ファイルがある場合の確認
        if existing_config_files and not force:
            console.print("[yellow]以下の設定ファイルが既に存在します:[/yellow]")
            for filename in existing_config_files:
                console.print(f"  - {filename}")

            if not Confirm.ask("上書きしますか？"):
                console.print("[yellow]初期化をキャンセルしました。[/yellow]")
                return

        # テンプレートファイルを作成
        _create_template_files(project_root, force)

        # 実際の設定ファイルを作成
        _create_actual_config_files(project_root, force)

        # サンプルワークフローを用意
        _ensure_sample_workflows(project_root)

        # .gitignore への追加提案
        _handle_gitignore_update(project_root)

        # 環境変数の状況を表示
        _show_environment_status()

        # 成功メッセージと次のステップ
        console.print("\n[green]🎉 初期化が完了しました！[/green]")
        console.print("\n[bold]次のステップ:[/bold]")
        console.print("1. 必要に応じて設定ファイルを編集")
        console.print("2. [cyan]ci-run doctor[/cyan] で環境をチェック")

    except ConfigurationError:
        raise
    except Exception as e:
        raise ConfigurationError(
            "初期化処理中にエラーが発生しました", "プロジェクトディレクトリの権限を確認してください"
        ) from e


def _create_template_files(project_root: Path, force: bool = False) -> None:
    """テンプレートファイルを作成（参考用）"""
    template_files = [
        (".actrc.example", ACTRC_TEMPLATE),
        ("ci-helper.toml.example", CI_HELPER_TOML_TEMPLATE),
        (".env.example", ENV_EXAMPLE_TEMPLATE),
    ]

    for filename, template_content in template_files:
        file_path = project_root / filename

        # 既存のテンプレートファイルの処理
        if file_path.exists() and not force:
            console.print(f"[dim]✓ {filename} は既に存在します（保持）[/dim]")
            continue

        try:
            file_path.write_text(template_content, encoding="utf-8")
            if file_path.exists() and force:
                console.print(f"[green]✓[/green] {filename} を上書きしました")
            else:
                console.print(f"[green]✓[/green] {filename} を作成しました")
        except OSError as e:
            console.print(f"[red]✗[/red] {filename} の作成に失敗しました: {e}")


def _create_actual_config_files(project_root: Path, force: bool) -> None:
    """テンプレートから実際の設定ファイルを作成"""
    # テンプレートから実際の設定ファイルを生成
    config_mappings = [
        (".actrc.example", ".actrc", "act の設定ファイル"),
        ("ci-helper.toml.example", "ci-helper.toml", "ci-helper の設定ファイル"),
        (".env.example", ".env", "環境変数ファイル"),
    ]

    for template_name, actual_name, description in config_mappings:
        template_path = project_root / template_name
        actual_path = project_root / actual_name

        if template_path.exists():
            # 既存ファイルがある場合の処理
            if actual_path.exists() and not force:
                console.print(f"[dim]✓ {actual_name} は既に存在します（保持）[/dim]")
                continue

            try:
                # テンプレートを読み込み、環境固有の値で置換
                template_content = template_path.read_text(encoding="utf-8")
                actual_content = _customize_template_content(template_content, actual_name)
                _write_config_file(actual_path, actual_content, description, force)
            except OSError as e:
                console.print(f"[red]✗[/red] {actual_name} の作成に失敗しました: {e}")
        else:
            console.print(f"[yellow]⚠[/yellow] {template_name} が見つかりません")


def _ensure_sample_workflows(project_root: Path) -> None:
    """サンプルワークフローを作成"""
    workflows_dir = project_root / ".github" / "workflows"
    try:
        workflows_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        console.print(f"[red]✗[/red] ワークフローディレクトリの作成に失敗しました: {e}")
        return

    existing_workflows = list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))
    if existing_workflows:
        console.print(
            f"[dim]✓ {workflows_dir.relative_to(project_root)}/ に既存のワークフローが見つかりました ({len(existing_workflows)} 件)[/dim]"
        )
        return

    sample_workflow_path = workflows_dir / "ci-helper-sample.yml"
    try:
        sample_workflow_path.write_text(SAMPLE_WORKFLOW_TEMPLATE.strip() + "\n", encoding="utf-8")
        relative_path = sample_workflow_path.relative_to(project_root)
        console.print(f"[green]✓[/green] {relative_path} を作成しました (サンプルワークフロー)")
    except OSError as e:
        console.print(f"[red]✗[/red] サンプルワークフローの作成に失敗しました: {e}")


def _customize_template_content(template_content: str, filename: str) -> str:
    """テンプレート内容を環境固有の値でカスタマイズ"""

    # 環境情報を収集
    env_info = _collect_environment_info()

    # ファイル種別に応じたカスタマイズ
    if filename == ".env":
        return _customize_env_template(template_content, env_info)
    elif filename == "ci-helper.toml":
        return _customize_toml_template(template_content, env_info)
    elif filename == ".actrc":
        return _customize_actrc_template(template_content, env_info)

    return template_content


def _collect_environment_info() -> dict:
    """環境情報を収集"""
    import os
    import platform

    return {
        "os": platform.system().lower(),
        "arch": platform.machine().lower(),
        "user": os.getenv("USER", "user"),
        "home": os.getenv("HOME", str(Path.home())),
        "github_token_exists": any(
            key in os.environ for key in ["GITHUB_TOKEN", "GITHUB_PERSONAL_ACCESS_TOKEN", "GH_TOKEN"]
        ),
        "openai_key_exists": "OPENAI_API_KEY" in os.environ,
        "anthropic_key_exists": "ANTHROPIC_API_KEY" in os.environ,
        "ollama_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    }


def _customize_env_template(template_content: str, env_info: dict) -> str:
    """.env テンプレートをカスタマイズ"""
    content = template_content

    # 既存の環境変数に応じてコメントを調整
    if env_info["github_token_exists"]:
        content = content.replace(
            "# GITHUB_TOKEN=your_github_token_here", "# GitHub token is already set in system environment variables"
        )

    if env_info["openai_key_exists"]:
        content = content.replace(
            "# OPENAI_API_KEY=sk-proj-your-openai-api-key-here",
            "# OpenAI API key is already set in system environment variables",
        )

    if env_info["anthropic_key_exists"]:
        content = content.replace(
            "# ANTHROPIC_API_KEY=sk-ant-your-anthropic-api-key-here",
            "# Anthropic API key is already set in system environment variables",
        )

    # Ollama URLを環境変数から取得
    content = content.replace("# OLLAMA_BASE_URL=http://localhost:11434", f"# OLLAMA_BASE_URL={env_info['ollama_url']}")

    return content


def _customize_toml_template(template_content: str, env_info: dict) -> str:
    """ci-helper.toml テンプレートをカスタマイズ"""
    # 現在はテンプレートをそのまま使用
    return template_content


def _customize_actrc_template(template_content: str, env_info: dict) -> str:
    """.actrc テンプレートをカスタマイズ"""
    # 現在はテンプレートをそのまま使用
    return template_content


def _generate_ci_helper_toml_content_legacy(project_root: Path) -> str:
    """汎用的な ci-helper.toml の内容を生成（環境固有の設定は避ける）"""
    return """# ci-helper configuration file
# Generated by ci-helper

[ci-helper]
# Verbose output
verbose = false

# Log directory
log_dir = ".ci-helper/logs"

# Cache directory
cache_dir = ".ci-helper/cache"

# Reports directory
reports_dir = ".ci-helper/reports"

# Maximum log file size in MB
max_log_size_mb = 100

# Maximum cache size in MB
max_cache_size_mb = 500

# Timeout for CI operations in seconds (30 minutes)
timeout_seconds = 1800

# Save logs after execution
save_logs = true

# Context lines to show around failures
context_lines = 3

# Docker image for act
act_image = "ghcr.io/catthehacker/ubuntu:full-latest"

# AI統合設定
[ai]
default_provider = "openai"  # デフォルトAIプロバイダー: openai, anthropic, local
cache_enabled = true         # AIレスポンスキャッシュを有効にするか
cache_ttl_hours = 24        # キャッシュの有効期限（時間）
interactive_timeout = 300    # 対話モードのタイムアウト（秒）
parallel_requests = false    # 並列リクエストを有効にするか

# OpenAI設定
[ai.providers.openai]
default_model = "gpt-4o"                    # デフォルトモデル
available_models = ["gpt-4o", "gpt-4o-mini"]  # 利用可能なモデル
timeout_seconds = 30                        # APIタイムアウト（秒）
max_retries = 3                            # 最大リトライ回数

# Anthropic設定
[ai.providers.anthropic]
default_model = "claude-3-5-sonnet-20241022"
available_models = [
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022"
]
timeout_seconds = 30
max_retries = 3

# ローカルLLM設定（Ollama）
[ai.providers.local]
default_model = "llama3.2"                  # デフォルトローカルモデル
available_models = ["llama3.2", "codellama", "mistral"]
timeout_seconds = 60                        # ローカルLLMは時間がかかる場合がある
max_retries = 2
base_url = "http://localhost:11434"         # OllamaサーバーURL

# コスト管理設定
[ai.cost_limits]
monthly_usd = 50.0          # 月間使用コスト上限（USD）
per_request_usd = 1.0       # 1回のリクエストあたりのコスト上限（USD）
warning_threshold = 0.8     # 警告を表示する閾値（制限の80%で警告）

# キャッシュ設定
[ai.cache]
max_size_mb = 100          # キャッシュの最大サイズ（MB）
cleanup_threshold = 0.9    # 自動クリーンアップを開始する閾値
auto_cleanup = true        # 自動クリーンアップを有効にするか
compression = true         # キャッシュデータの圧縮を有効にするか

# セキュリティ設定
[ai.security]
mask_secrets = true                          # ログ内のシークレットを自動マスクするか
allowed_domains = [                          # 接続を許可するドメイン
    "api.openai.com",
    "api.anthropic.com"
]
verify_ssl = true                           # SSL証明書の検証を行うか

# ログ処理設定
[ai.log_processing]
max_tokens = 100000        # AIに送信する最大トークン数
compression_ratio = 0.3    # ログ圧縮の目標比率
preserve_errors = true     # エラー情報を優先的に保持するか
context_lines = 5          # エラー前後の文脈行数

# パフォーマンス設定
[ai.performance]
concurrent_requests = 2    # 同時実行するリクエスト数
request_delay_ms = 100     # リクエスト間の遅延時間（ミリ秒）
memory_limit_mb = 512      # AI処理で使用する最大メモリ（MB）
"""


def _generate_env_content_legacy() -> str:
    """環境変数ファイルの内容を生成"""
    import os

    # 既存の環境変数をチェック
    github_token_exists = any(key in os.environ for key in ["GITHUB_TOKEN", "GITHUB_PERSONAL_ACCESS_TOKEN", "GH_TOKEN"])
    openai_key_exists = "OPENAI_API_KEY" in os.environ
    anthropic_key_exists = "ANTHROPIC_API_KEY" in os.environ

    if github_token_exists:
        github_token_comment = "# GitHub token is already set in system environment variables"
    else:
        github_token_comment = "# GITHUB_TOKEN=your_github_token_here"

    if openai_key_exists:
        openai_key_comment = "# OpenAI API key is already set in system environment variables"
    else:
        openai_key_comment = "# OPENAI_API_KEY=sk-proj-your-openai-api-key-here"

    if anthropic_key_exists:
        anthropic_key_comment = "# Anthropic API key is already set in system environment variables"
    else:
        anthropic_key_comment = "# ANTHROPIC_API_KEY=sk-ant-your-anthropic-api-key-here"

    return f"""# Environment variables for ci-helper
# Generated by ci-helper

# GitHub token for API access
{github_token_comment}

# Docker registry credentials (if needed)
# DOCKER_USERNAME=your_username
# DOCKER_PASSWORD=your_password

# AI統合設定
# 重要: APIキーは機密情報です。このファイルを.gitignoreに追加してください

# AIプロバイダーのAPIキー（必須）
# OpenAI APIキー（https://platform.openai.com/api-keys で取得）
{openai_key_comment}

# Anthropic APIキー（https://console.anthropic.com/keys で取得）
{anthropic_key_comment}

# ローカルLLM設定（Ollama使用時）
# OLLAMA_BASE_URL=http://localhost:11434

# AI設定の上書き（ci-helper.tomlの設定より優先される）
# CI_HELPER_AI_PROVIDER=openai                    # デフォルトプロバイダー
# CI_HELPER_AI_MODEL=gpt-4o                       # デフォルトモデル
# CI_HELPER_AI_CACHE_ENABLED=true                 # キャッシュ有効化

# コスト制限の上書き
# CI_HELPER_AI_COST_LIMITS_MONTHLY_USD=25.0       # 月間制限を25ドルに
# CI_HELPER_AI_COST_LIMITS_PER_REQUEST_USD=0.5    # 1回あたり50セントに制限

# Custom environment variables for your workflows
# Add your project-specific environment variables below

# Note: System environment variables take precedence over .env file
# Current status:
#   GitHub token: {"✓ Found in system" if github_token_exists else "✗ Not found"}
#   OpenAI API key: {"✓ Found in system" if openai_key_exists else "✗ Not found"}
#   Anthropic API key: {"✓ Found in system" if anthropic_key_exists else "✗ Not found"}
"""


def _show_environment_status() -> None:
    """環境変数の状況を表示"""
    import os

    console.print("\n[bold blue]📋 環境変数の状況[/bold blue]")

    # GitHub トークンの確認
    github_tokens = ["GITHUB_TOKEN", "GITHUB_PERSONAL_ACCESS_TOKEN", "GH_TOKEN"]
    github_token_found = None

    for token_name in github_tokens:
        if token_name in os.environ:
            github_token_found = token_name
            break

    if github_token_found:
        console.print(f"[green]✓[/green] GitHub トークン: {github_token_found} が設定済み")
        console.print("  [dim].env ファイルの GitHub トークン設定は無視されます[/dim]")
    else:
        console.print("[yellow]⚠[/yellow] GitHub トークンが見つかりません")
        console.print("  [dim].env ファイルで設定するか、システム環境変数を設定してください[/dim]")

    # Docker 関連の確認
    docker_vars = ["DOCKER_USERNAME", "DOCKER_PASSWORD", "DOCKER_TOKEN"]
    docker_found = [var for var in docker_vars if var in os.environ]

    if docker_found:
        console.print(f"[green]✓[/green] Docker 認証情報: {', '.join(docker_found)} が設定済み")
    else:
        console.print("[dim]ℹ[/dim] Docker 認証情報は設定されていません（必要に応じて設定）")


def _write_config_file(file_path: Path, content: str, description: str, force: bool = False) -> None:
    """設定ファイルを書き込み"""
    try:
        if file_path.exists() and force:
            console.print(f"[green]✓[/green] {file_path.name} を上書きしました ({description})")
        else:
            console.print(f"[green]✓[/green] {file_path.name} を作成しました ({description})")

        file_path.write_text(content, encoding="utf-8")
    except OSError as e:
        console.print(f"[red]✗[/red] {file_path.name} の作成に失敗しました: {e}")


def _handle_gitignore_update(project_root: Path) -> None:
    """gitignore ファイルの更新処理"""
    gitignore_path = project_root / ".gitignore"

    if gitignore_path.exists():
        gitignore_content = gitignore_path.read_text(encoding="utf-8")
        if ".ci-helper/" not in gitignore_content:
            console.print("\n[yellow]推奨:[/yellow] .gitignore に以下を追加することをお勧めします:")
            console.print(GITIGNORE_ADDITIONS)

            if Confirm.ask(".gitignore に自動追加しますか？"):
                try:
                    with gitignore_path.open("a", encoding="utf-8") as f:
                        f.write(GITIGNORE_ADDITIONS)
                    console.print("[green]✓[/green] .gitignore を更新しました")
                except OSError as e:
                    console.print(f"[red]✗[/red] .gitignore の更新に失敗しました: {e}")
    else:
        console.print("\n[yellow]推奨:[/yellow] .gitignore ファイルを作成することをお勧めします")
        if Confirm.ask(".gitignore を作成しますか？"):
            try:
                gitignore_path.write_text(GITIGNORE_ADDITIONS, encoding="utf-8")
                console.print("[green]✓[/green] .gitignore を作成しました")
            except OSError as e:
                console.print(f"[red]✗[/red] .gitignore の作成に失敗しました: {e}")


def _copy_template_to_actual(template_path: Path, actual_path: Path, force: bool = False) -> bool:
    """テンプレートファイルを実際の設定ファイルにコピー

    Args:
        template_path: テンプレートファイルのパス
        actual_path: 実際の設定ファイルのパス
        force: 既存ファイルを強制上書きするか

    Returns:
        コピーが成功したかどうか
    """
    if actual_path.exists() and not force:
        return False

    try:
        template_content = template_path.read_text(encoding="utf-8")
        actual_path.write_text(template_content, encoding="utf-8")
        return True
    except OSError:
        return False


@click.command()
@click.option(
    "--force",
    is_flag=True,
    help="既存ファイルを上書きします",
)
def setup(force: bool) -> None:
    """テンプレートから実際の設定ファイルを作成します

    .example ファイルから実際の設定ファイルを作成します。
    """
    project_root = Path.cwd()

    # コピーするファイルの定義
    copy_files = [
        (".actrc.example", ".actrc"),
        ("ci-helper.toml.example", "ci-helper.toml"),
        (".env.example", ".env"),
    ]

    copied_files = []
    skipped_files = []

    for template_name, actual_name in copy_files:
        template_path = project_root / template_name
        actual_path = project_root / actual_name

        if not template_path.exists():
            console.print(
                f"[yellow]⚠[/yellow] {template_name} が見つかりません。"
                "先に [cyan]ci-run init[/cyan] を実行してください。"
            )
            continue

        if _copy_template_to_actual(template_path, actual_path, force):
            copied_files.append(actual_name)
            console.print(f"[green]✓[/green] {actual_name} を作成しました")
        else:
            skipped_files.append(actual_name)
            console.print(f"[yellow]⚠[/yellow] {actual_name} は既に存在します（--force で上書き可能）")

    if copied_files:
        console.print(f"\n[green]🎉 {len(copied_files)} 個のファイルを作成しました！[/green]")
        console.print("\n[bold]次のステップ:[/bold]")
        console.print("1. 作成された設定ファイルを必要に応じて編集")
        console.print("2. [cyan]ci-run doctor[/cyan] で環境をチェック")

    if skipped_files:
        console.print(f"\n[yellow]{len(skipped_files)} 個のファイルをスキップしました。[/yellow]")
