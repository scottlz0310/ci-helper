# カスタムパターン作成ガイド

## 概要

CI-Helperでは、プロジェクト固有のエラーパターンに対応するため、カスタムパターンを作成できます。このガイドでは、カスタムパターンの作成方法、テスト、管理について説明します。

## カスタムパターンの基本構造

カスタムパターンは JSON 形式で定義し、以下の構造を持ちます：

```json
{
  "id": "unique_pattern_id",
  "name": "パターン名",
  "description": "パターンの説明",
  "category": "custom",
  "regex_patterns": [
    "正規表現パターン1",
    "正規表現パターン2"
  ],
  "keywords": [
    "キーワード1",
    "キーワード2"
  ],
  "context_requirements": [
    "必要なコンテキスト条件"
  ],
  "confidence_base": 0.8,
  "success_rate": 0.0,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z",
  "user_defined": true,
  "fix_template_id": "対応する修正テンプレートID"
}
```

## パターン作成の手順

### 1. エラーログの分析

まず、対象となるエラーログを詳しく分析します：

```bash
# 未知のエラーを含むログを分析
ci-run analyze --show-unmatched-errors

# 特定のログファイルから未知エラーを抽出
ci-run extract-errors --log-file path/to/logfile.txt --unknown-only
```

### 2. パターンの設計

#### 正規表現パターンの作成

エラーメッセージの特徴的な部分を正規表現で表現します：

```regex
# 例：カスタムビルドツールのエラー
"MyBuildTool: Error \\d+: .* failed"

# 例：特定のライブラリのエラー
"CustomLib\\[ERROR\\]: .* not found in .*"

# 例：プロジェクト固有の設定エラー
"Config validation failed: .* is required but not set"
```

#### キーワードの選定

エラーに頻出する重要なキーワードを選定します：

```json
"keywords": [
  "MyBuildTool",
  "CustomLib",
  "Config validation failed",
  "required but not set"
]
```

### 3. パターンファイルの作成

カスタムパターンは `data/patterns/custom/user_patterns.json` に追加します：

```json
{
  "patterns": [
    {
      "id": "my_build_tool_error",
      "name": "MyBuildToolエラー",
      "description": "カスタムビルドツールの一般的なエラー",
      "category": "build",
      "regex_patterns": [
        "MyBuildTool: Error \\d+: .* failed",
        "MyBuildTool.*compilation error"
      ],
      "keywords": [
        "MyBuildTool",
        "compilation error",
        "build failed"
      ],
      "context_requirements": [
        "build_log"
      ],
      "confidence_base": 0.8,
      "success_rate": 0.0,
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:00:00Z",
      "user_defined": true,
      "fix_template_id": "my_build_tool_fix"
    }
  ]
}
```

### 4. 修正テンプレートの作成

対応する修正テンプレートも作成します：

```json
{
  "templates": [
    {
      "id": "my_build_tool_fix",
      "name": "MyBuildToolエラー修正",
      "description": "MyBuildToolの設定を修正",
      "pattern_ids": ["my_build_tool_error"],
      "fix_steps": [
        {
          "type": "file_modification",
          "description": "ビルド設定ファイルを更新",
          "file_path": "build.config",
          "action": "replace",
          "content": "# 修正された設定内容",
          "validation": "MyBuildTool --validate-config"
        }
      ],
      "risk_level": "medium",
      "estimated_time": "5分",
      "success_rate": 0.0,
      "prerequisites": [
        "MyBuildToolがインストールされている"
      ],
      "validation_steps": [
        "設定ファイルの構文チェック",
        "ビルドテストの実行"
      ]
    }
  ]
}
```

## パターンのテスト

### 1. 構文検証

```bash
# パターンファイルの構文をチェック
ci-run validate-patterns --file data/patterns/custom/user_patterns.json

# 全カスタムパターンを検証
ci-run validate-patterns --custom-only
```

### 2. マッチングテスト

```bash
# 特定のログでパターンをテスト
ci-run test-pattern --pattern-id my_build_tool_error --log-file test.log

# パターンの正規表現を直接テスト
ci-run test-regex --pattern "MyBuildTool: Error \\d+: .* failed" --text "MyBuildTool: Error 123: compilation failed"
```

### 3. 統合テスト

```bash
# カスタムパターンを含めて分析実行
ci-run analyze --include-custom-patterns

# 特定のカテゴリのみテスト
ci-run analyze --categories custom --log-file test.log
```

## 高度なパターン作成

### 1. 変数キャプチャ

正規表現で変数をキャプチャして修正テンプレートで使用：

```json
{
  "regex_patterns": [
    "Package '(?P<package_name>[^']+)' not found",
    "Missing dependency: (?P<dependency_name>\\S+)"
  ]
}
```

修正テンプレートでの使用：

```json
{
  "fix_steps": [
    {
      "type": "command",
      "description": "不足パッケージをインストール",
      "command": "npm install {package_name}",
      "validation": "npm list {package_name}"
    }
  ]
}
```

### 2. 条件付きマッチング

コンテキスト要件を使用した条件付きマッチング：

```json
{
  "context_requirements": [
    "file_exists:package.json",
    "log_contains:npm",
    "not_contains:yarn"
  ]
}
```

### 3. 複合パターン

複数の条件を組み合わせたパターン：

```json
{
  "regex_patterns": [
    "Error: .*",
    "Failed: .*"
  ],
  "keywords": [
    "MyCustomTool",
    "specific_error_code"
  ],
  "context_requirements": [
    "log_section:build",
    "file_exists:custom.config"
  ]
}
```

## パターンの管理

### 1. パターンの更新

```bash
# パターンの成功率を更新
ci-run update-pattern-stats --pattern-id my_build_tool_error --success-rate 0.85

# パターンの信頼度を調整
ci-run adjust-confidence --pattern-id my_build_tool_error --confidence 0.9
```

### 2. パターンの無効化

```bash
# 特定のパターンを無効化
ci-run disable-pattern --pattern-id my_build_tool_error

# カテゴリ全体を無効化
ci-run disable-category --category custom
```

### 3. パターンの削除

```bash
# パターンを削除（注意：元に戻せません）
ci-run remove-pattern --pattern-id my_build_tool_error --confirm
```

## パターンの共有

### 1. エクスポート

```bash
# 特定のパターンをエクスポート
ci-run export-pattern --pattern-id my_build_tool_error --output my_pattern.json

# カテゴリ全体をエクスポート
ci-run export-patterns --category custom --output custom_patterns.json
```

### 2. インポート

```bash
# パターンファイルをインポート
ci-run import-patterns --file shared_patterns.json

# 既存パターンとの競合を確認
ci-run import-patterns --file shared_patterns.json --check-conflicts
```

### 3. パターンライブラリ

コミュニティで共有されているパターンライブラリの利用：

```bash
# 利用可能なライブラリを検索
ci-run search-pattern-library --query "docker"

# ライブラリからパターンをインストール
ci-run install-pattern-library --name "docker-common-errors"
```

## ベストプラクティス

### 1. パターン設計

- **具体的すぎず、汎用的すぎない**バランスを保つ
- **複数の正規表現**でエラーのバリエーションをカバー
- **キーワード**でノイズを削減
- **コンテキスト要件**で誤検出を防ぐ

### 2. テストの徹底

- 実際のエラーログでテスト
- 偽陽性（誤検出）のチェック
- 偽陰性（見逃し）のチェック
- 他のパターンとの競合確認

### 3. 継続的改善

- 成功率の定期的な確認
- ユーザーフィードバックの活用
- パターンの定期的な見直し
- 新しいエラータイプへの対応

### 4. ドキュメント化

- パターンの目的と対象を明記
- 修正手順の詳細な説明
- 前提条件と制限事項の記載
- 使用例とテストケースの提供

## トラブルシューティング

### よくある問題

#### 1. パターンがマッチしない

```bash
# デバッグモードで詳細確認
ci-run analyze --debug --pattern-id my_build_tool_error

# 正規表現のテスト
ci-run test-regex --pattern "your_regex_here" --text "test_text"
```

#### 2. 誤検出が多い

- キーワードを追加してノイズを削減
- コンテキスト要件を厳しくする
- 正規表現をより具体的にする

#### 3. 修正が失敗する

- 前提条件の確認
- 修正ステップの検証
- ファイルパスや権限の確認

### デバッグコマンド

```bash
# パターンマッチングの詳細ログ
ci-run analyze --debug-patterns

# 特定パターンの詳細情報
ci-run pattern-info --pattern-id my_build_tool_error

# マッチング統計の表示
ci-run pattern-stats --detailed
```

## 例：実際のカスタムパターン

### Python仮想環境エラー

```json
{
  "id": "python_venv_not_activated",
  "name": "Python仮想環境未アクティベート",
  "description": "仮想環境がアクティベートされていないエラー",
  "category": "dependency",
  "regex_patterns": [
    "ModuleNotFoundError: No module named '.*'",
    "ImportError: No module named .*",
    "pip: command not found"
  ],
  "keywords": [
    "ModuleNotFoundError",
    "ImportError",
    "pip",
    "command not found"
  ],
  "context_requirements": [
    "file_exists:requirements.txt",
    "file_exists:venv/",
    "not_contains:source venv/bin/activate"
  ],
  "confidence_base": 0.85,
  "fix_template_id": "activate_python_venv"
}
```

### Docker Compose設定エラー

```json
{
  "id": "docker_compose_version_error",
  "name": "Docker Compose バージョンエラー",
  "description": "Docker Composeファイルのバージョン互換性エラー",
  "category": "config",
  "regex_patterns": [
    "version .* is not supported",
    "Unsupported Compose file version",
    "Invalid compose file.*version"
  ],
  "keywords": [
    "docker-compose",
    "version",
    "not supported",
    "Invalid compose file"
  ],
  "context_requirements": [
    "file_exists:docker-compose.yml",
    "log_contains:docker-compose"
  ],
  "confidence_base": 0.9,
  "fix_template_id": "fix_docker_compose_version"
}
```

## 参考資料

- [正規表現リファレンス](https://docs.python.org/3/library/re.html)
- [パターン認識機能使用ガイド](pattern-recognition-guide.md)
- [トラブルシューティングガイド](troubleshooting-pattern-recognition.md)
- [CI-Helper設定リファレンス](ai-configuration.md)
