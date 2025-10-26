# CLI ログ整形機能 設計書

## 概要

本設計書は、CI-HelperのCLIメニューシステムにログ整形機能を追加するための技術設計を定義します。この機能により、ユーザーは対話的メニューから直接ログを様々な形式（AI消費用、人間可読、JSON等）に整形でき、コマンドライン引数を使用した非対話的な実行も可能になります。

## アーキテクチャ

### システム構成

```
src/ci_helper/
├── cli.py                           # メインCLIエントリーポイント（既存）
├── commands/
│   ├── logs.py                      # 既存ログコマンド（拡張）
│   └── format_logs.py               # 新規：ログ整形専用コマンド
├── ui/
│   ├── menu_system.py               # 既存メニューシステム（拡張）
│   └── command_menus.py             # 既存コマンドメニュー（拡張）
├── formatters/
│   ├── __init__.py                  # 新規：フォーマッターパッケージ
│   ├── base_formatter.py            # 新規：基底フォーマッタークラス
│   ├── ai_context_formatter.py      # 新規：AI消費用フォーマッター
│   ├── human_readable_formatter.py  # 新規：人間可読フォーマッター
│   └── json_formatter.py            # 新規：JSON専用フォーマッター
└── core/
    ├── ai_formatter.py              # 既存（統合対象）
    └── log_manager.py               # 既存（拡張）
```

### 設計原則

1. **既存コードとの統合**: 現在の`AIFormatter`クラスを基盤として活用
2. **モジュラー設計**: フォーマッター機能を独立したモジュールとして分離
3. **一貫性**: メニューシステムとコマンドライン両方で同じ整形エンジンを使用
4. **拡張性**: 新しいフォーマット形式を容易に追加可能な設計
5. **セキュリティ**: 既存のシークレットサニタイズ機能を継承

## コンポーネント設計

### 1. 基底フォーマッタークラス

```python
# src/ci_helper/formatters/base_formatter.py
from abc import ABC, abstractmethod
from typing import Any, Dict
from ..core.models import ExecutionResult

class BaseLogFormatter(ABC):
    """ログフォーマッターの基底クラス"""
    
    def __init__(self, sanitize_secrets: bool = True):
        self.sanitize_secrets = sanitize_secrets
        if sanitize_secrets:
            from ..core.security import SecurityValidator
            self.security_validator = SecurityValidator()
    
    @abstractmethod
    def format(self, execution_result: ExecutionResult, **options) -> str:
        """ログを指定形式でフォーマット"""
        pass
    
    @abstractmethod
    def get_format_name(self) -> str:
        """フォーマット名を取得"""
        pass
    
    def _sanitize_content(self, content: str) -> str:
        """コンテンツのサニタイズ（共通処理）"""
        if not self.sanitize_secrets:
            return content
        return self.security_validator.secret_detector.sanitize_content(content)
```

### 2. AI消費用フォーマッター

```python
# src/ci_helper/formatters/ai_context_formatter.py
class AIContextFormatter(BaseLogFormatter):
    """AI分析に最適化されたコンテキスト強化フォーマッター"""
    
    def format(self, execution_result: ExecutionResult, **options) -> str:
        """AIに最適化されたMarkdownを生成"""
        sections = [
            self._format_quick_summary(execution_result),
            self._format_critical_failures(execution_result),
            self._format_context_analysis(execution_result),
            self._format_suggested_fixes(execution_result),
            self._format_related_files(execution_result),
            self._format_full_logs(execution_result),
        ]
        return "\n\n---\n\n".join(filter(None, sections))
    
    def _format_critical_failures(self, execution_result: ExecutionResult) -> str:
        """クリティカルな失敗を優先度順に整形"""
        failures = self._prioritize_failures(execution_result.all_failures)
        # 実装詳細...
    
    def _prioritize_failures(self, failures: list) -> list:
        """失敗を優先度順にソート"""
        # アサーションエラー、ファイル情報、スタックトレースの有無で優先度付け
```

### 3. 人間可読フォーマッター

```python
# src/ci_helper/formatters/human_readable_formatter.py
class HumanReadableFormatter(BaseLogFormatter):
    """人間が読みやすい形式のフォーマッター"""
    
    def format(self, execution_result: ExecutionResult, **options) -> str:
        """色付けと構造化された人間可読形式を生成"""
        # Rich ライブラリを使用した色付け出力
        # セクション分けされたレイアウト
        # 重要なエラー情報のハイライト表示
```

### 4. JSON専用フォーマッター

```python
# src/ci_helper/formatters/json_formatter.py
class JSONFormatter(BaseLogFormatter):
    """JSON形式専用フォーマッター"""
    
    def format(self, execution_result: ExecutionResult, **options) -> str:
        """構造化されたJSONデータを生成"""
        # 既存のAIFormatter.format_json()を基盤として拡張
        # プログラム的に解析可能な構造
```

### 5. フォーマッターマネージャー

```python
# src/ci_helper/formatters/__init__.py
class FormatterManager:
    """フォーマッター管理クラス"""
    
    def __init__(self):
        self.formatters = {
            'ai': AIContextFormatter(),
            'human': HumanReadableFormatter(),
            'json': JSONFormatter(),
            'markdown': self._get_legacy_formatter(),  # 既存AIFormatterとの互換性
        }
    
    def get_formatter(self, format_name: str) -> BaseLogFormatter:
        """指定されたフォーマッターを取得"""
        
    def list_available_formats(self) -> list[str]:
        """利用可能なフォーマット一覧を取得"""
```

## メニューシステム統合

### ログ管理サブメニューの拡張

既存の`_build_logs_submenu()`メソッドを拡張して、ログ整形オプションを追加：

```python
def _build_logs_submenu(self) -> Menu:
    """ログ管理サブメニューを構築（拡張版）"""
    return Menu(
        title="ログ管理メニュー",
        items=[
            # 既存項目
            MenuItem(key="1", title="ログ一覧表示", ...),
            MenuItem(key="2", title="最新ログ表示", ...),
            MenuItem(key="3", title="ログ比較", ...),
            
            # 新規追加項目
            MenuItem(
                key="4",
                title="ログ整形",
                description="ログを様々な形式で整形します",
                submenu=self._build_log_formatting_submenu(),
            ),
        ],
        show_back=True,
        show_quit=True,
    )

def _build_log_formatting_submenu(self) -> Menu:
    """ログ整形サブメニューを構築"""
    return Menu(
        title="ログ整形メニュー",
        items=[
            MenuItem(
                key="1",
                title="AI分析用フォーマット",
                description="AI分析に最適化されたMarkdown形式で出力",
                action=self._create_format_action("ai"),
            ),
            MenuItem(
                key="2",
                title="人間可読フォーマット",
                description="色付けされた構造化出力を生成",
                action=self._create_format_action("human"),
            ),
            MenuItem(
                key="3",
                title="JSON形式",
                description="構造化されたJSONデータを出力",
                action=self._create_format_action("json"),
            ),
            MenuItem(
                key="4",
                title="カスタム整形",
                description="整形パラメータをカスタマイズ",
                action=self._create_custom_format_action(),
            ),
        ],
        show_back=True,
        show_quit=True,
    )
```

## コマンドライン統合

### 新規コマンド: format-logs

```python
# src/ci_helper/commands/format_logs.py
@click.command()
@click.option(
    "--format", 
    "output_format",
    type=click.Choice(["ai", "human", "json", "markdown"], case_sensitive=False),
    default="ai",
    help="出力フォーマット（デフォルト: ai）"
)
@click.option(
    "--input", 
    "input_file",
    type=click.Path(exists=True, path_type=Path),
    help="入力ログファイル（省略時は最新ログを使用）"
)
@click.option(
    "--output", 
    "output_file",
    type=click.Path(path_type=Path),
    help="出力ファイル（省略時は標準出力）"
)
@click.option(
    "--filter-errors",
    is_flag=True,
    help="エラーのみをフィルタリング"
)
@click.option(
    "--verbose-level",
    type=click.Choice(["minimal", "normal", "detailed"], case_sensitive=False),
    default="normal",
    help="詳細レベル（デフォルト: normal）"
)
@click.pass_context
def format_logs(
    ctx: click.Context,
    output_format: str,
    input_file: Path | None,
    output_file: Path | None,
    filter_errors: bool,
    verbose_level: str,
) -> None:
    """ログを指定された形式で整形
    
    \b
    使用例:
      ci-run format-logs                           # 最新ログをAI形式で標準出力
      ci-run format-logs --format human           # 人間可読形式で出力
      ci-run format-logs --format json --output result.json  # JSON形式でファイル保存
      ci-run format-logs --input act_20240101.log --format ai  # 特定ログをAI形式で出力
    """
```

### 既存CLIへの統合

メインCLIの`cli.py`に新しいコマンドを登録：

```python
# cli.pyに追加
from .commands.format_logs import format_logs
cli.add_command(format_logs)
```

## データフロー

### 1. メニュー選択方式

```
ユーザー選択
    ↓
メニューシステム
    ↓
コマンドハンドラー
    ↓
FormatterManager
    ↓
適切なFormatter
    ↓
整形結果出力
```

### 2. コマンド指定実行方式

```
CLIコマンド
    ↓
format_logs関数
    ↓
FormatterManager
    ↓
適切なFormatter
    ↓
ファイル保存 or 標準出力
```

## 進行状況表示

### プログレスインジケーター

大きなログファイルの処理時に進行状況を表示：

```python
from rich.progress import Progress, SpinnerColumn, TextColumn

def format_with_progress(self, execution_result: ExecutionResult) -> str:
    """進行状況表示付きでフォーマット実行"""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=self.console,
    ) as progress:
        task = progress.add_task("ログを整形中...", total=None)
        
        # 整形処理実行
        result = self.format(execution_result)
        
        progress.update(task, description="完了")
        return result
```

## エラーハンドリング

### 1. ファイル関連エラー

- 存在しないログファイルの指定
- 出力ファイルの書き込み権限エラー
- ディスク容量不足

### 2. フォーマット関連エラー

- 不正なログファイル形式
- メモリ不足（大きなログファイル）
- フォーマッター初期化エラー

### 3. ユーザー入力エラー

- 無効なフォーマット指定
- 不正なパラメータ値

## セキュリティ考慮事項

### 1. シークレットサニタイズ

既存の`SecurityValidator`を活用：

```python
def _ensure_security(self, content: str) -> str:
    """セキュリティチェックとサニタイズ"""
    if self.sanitize_secrets:
        # APIキー、パスワード、トークンなどを検出・マスク
        content = self.security_validator.secret_detector.sanitize_content(content)
    return content
```

### 2. ファイルアクセス制御

- 出力ファイルのパス検証
- 上位ディレクトリへの書き込み防止
- 権限チェック

## パフォーマンス最適化

### 1. 大きなログファイルの処理

- ストリーミング処理の実装
- メモリ使用量の制限
- 部分的な読み込み

### 2. キャッシュ機能

- フォーマット結果のキャッシュ
- 同一ログファイルの重複処理回避

## テスト戦略

### 1. 単体テスト

- 各フォーマッタークラスの個別テスト
- エラーハンドリングのテスト
- セキュリティ機能のテスト

### 2. 統合テスト

- メニューシステムとの統合テスト
- コマンドライン実行のテスト
- ファイル入出力のテスト

### 3. パフォーマンステスト

- 大きなログファイルの処理時間測定
- メモリ使用量の監視

## 設定オプション

### ci-helper.toml拡張

```toml
[log_formatting]
# デフォルトフォーマット
default_format = "ai"

# セキュリティ設定
sanitize_secrets = true

# 出力設定
default_output_dir = "formatted_logs"
auto_timestamp = true

# パフォーマンス設定
max_file_size_mb = 100
enable_caching = true
```

## 互換性

### 既存機能との互換性

1. **AIFormatter**: 既存の`format_markdown()`と`format_json()`メソッドを継承
2. **ログコマンド**: 既存の`logs`コマンドの機能を保持
3. **メニューシステム**: 既存のメニュー構造を拡張

### 段階的移行

1. **フェーズ1**: 新しいフォーマッターの実装
2. **フェーズ2**: メニューシステムの統合
3. **フェーズ3**: コマンドライン統合
4. **フェーズ4**: 既存AIFormatterの統合

## 実装優先度

### 高優先度

- 基底フォーマッタークラス
- AI消費用フォーマッター
- メニューシステム統合

### 中優先度

- 人間可読フォーマッター
- コマンドライン統合
- 進行状況表示

### 低優先度

- JSON専用フォーマッター（既存機能で代替可能）
- 高度なカスタマイズ機能
- パフォーマンス最適化

## 成功指標

### 機能的指標

- 全フォーマット形式の正常動作
- メニューとコマンドライン両方での実行成功
- セキュリティ機能の正常動作

### 品質指標

- テストカバレッジ90%以上
- 大きなログファイル（10MB以上）の処理成功
- エラー処理の適切な動作

### ユーザビリティ指標

- メニューからの直感的な操作
- 明確なエラーメッセージ
- 適切な進行状況表示

---

この設計により、CI-Helperのログ整形機能は既存のアーキテクチャと調和しながら、要件定義書で定義されたすべての機能を実現できます。
