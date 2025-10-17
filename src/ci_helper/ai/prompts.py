"""
プロンプトテンプレート管理

AI分析用のプロンプトテンプレートを管理し、エラータイプや分析目的に応じて
適切なプロンプトを生成します。
"""

from __future__ import annotations

import re
from pathlib import Path

from ..core.models import FailureType
from .exceptions import ConfigurationError
from .models import AnalysisResult


class PromptManager:
    """プロンプトテンプレート管理クラス"""

    def __init__(self, config_path: Path | None = None, custom_templates: dict[str, str] | None = None):
        """プロンプトマネージャーを初期化

        Args:
            config_path: カスタムテンプレートファイルのパス
            custom_templates: カスタムテンプレートの辞書
        """
        self.templates = self._load_default_templates()
        self.custom_templates = custom_templates or {}

        # カスタムテンプレートファイルがある場合は読み込み
        if config_path and config_path.exists():
            self._load_templates_from_file(config_path)

    def _load_default_templates(self) -> dict[str, str]:
        """デフォルトプロンプトテンプレートを読み込み"""
        return {
            "analysis": self._get_default_analysis_template(),
            "fix_suggestion": self._get_default_fix_template(),
            "interactive": self._get_default_interactive_template(),
            "error_specific": {
                "build_failure": self._get_build_failure_template(),
                "test_failure": self._get_test_failure_template(),
                "assertion": self._get_assertion_template(),
                "timeout": self._get_timeout_template(),
                "error": self._get_error_template(),
            },
        }

    def _get_default_analysis_template(self) -> str:
        """デフォルト分析プロンプトテンプレート"""
        return """あなたはCI/CDパイプラインの専門家です。以下のCI実行ログを分析し、問題の根本原因を特定してください。

## 分析の観点
1. **エラーの種類**: ビルドエラー、テストエラー、設定エラーなど
2. **根本原因**: 技術的な原因と背景
3. **影響範囲**: どの部分に影響するか
4. **緊急度**: 修正の優先度

## 出力形式
以下の形式で回答してください：

### 🔍 分析サマリー
[問題の概要を1-2文で]

### 🚨 検出されたエラー
- **エラータイプ**: [エラーの分類]
- **発生箇所**: [ファイル名:行番号]
- **エラーメッセージ**: [主要なエラーメッセージ]

### 🔧 根本原因
[技術的な原因の詳細説明]

### 📊 影響範囲
- **影響度**: [高/中/低]
- **影響する機能**: [具体的な機能名]

### ⚡ 推奨アクション
1. [具体的な修正手順1]
2. [具体的な修正手順2]
3. [予防策]

## 分析対象ログ:
{context}"""

    def _get_default_fix_template(self) -> str:
        """デフォルト修正提案プロンプトテンプレート"""
        return """以下のCI/CDエラー分析結果に基づいて、具体的な修正方法を提案してください。

## 修正提案の要件
1. **実行可能**: すぐに適用できる具体的な手順
2. **安全性**: 既存機能への影響を最小限に
3. **検証方法**: 修正後の確認手順も含める

## 出力形式
### 🛠️ 修正提案

#### 修正1: [修正タイトル]
**優先度**: [高/中/低]
**推定工数**: [時間の目安]

**変更内容**:
```diff
[変更前後のコード差分]
```

**手順**:
1. [具体的な手順1]
2. [具体的な手順2]

**検証方法**:
- [テスト方法1]
- [テスト方法2]

**注意点**:
- [重要な注意事項]

## 分析結果:
{analysis_result}

## 元のログ:
{context}"""

    def _get_default_interactive_template(self) -> str:
        """デフォルト対話プロンプトテンプレート"""
        return """あなたはCI/CDトラブルシューティングの専門アシスタントです。
開発者との対話を通じて、CI/CDの問題を段階的に解決していきます。

## 対話の方針
1. **段階的アプローチ**: 複雑な問題を小さな部分に分解
2. **実践的**: 実際に試せる具体的な提案
3. **教育的**: 問題の背景も説明して理解を深める
4. **効率的**: 最も可能性の高い原因から調査

## 利用可能なコマンド
- `/help`: 利用可能なコマンドを表示
- `/summary`: 現在の問題の要約を表示
- `/logs`: 関連ログの再表示
- `/fix`: 修正提案の生成
- `/exit`: セッション終了

## 会話履歴:
{conversation_history}

## 現在のコンテキスト:
{context}

開発者からの質問や要求に対して、親切で実用的な回答を提供してください。"""

    def _get_build_failure_template(self) -> str:
        """ビルド失敗専用プロンプトテンプレート"""
        return """ビルド失敗の専門分析を行います。以下の観点で詳細に分析してください：

## ビルド失敗分析の観点
1. **依存関係**: パッケージ、ライブラリの問題
2. **環境設定**: 環境変数、設定ファイルの問題
3. **コンパイル**: 構文エラー、型エラー
4. **リソース**: メモリ、ディスク容量の問題

## 特に注目すべき点
- パッケージマネージャーのエラー（npm, pip, maven等）
- 環境変数の不足や設定ミス
- バージョン互換性の問題
- ビルドツールの設定エラー

{context}"""

    def _get_test_failure_template(self) -> str:
        """テスト失敗専用プロンプトテンプレート"""
        return """テスト失敗の専門分析を行います。以下の観点で詳細に分析してください：

## テスト失敗分析の観点
1. **テストケース**: 失敗したテストの内容
2. **アサーション**: 期待値と実際の値の差異
3. **テスト環境**: テスト実行環境の問題
4. **データ**: テストデータやモックの問題

## 特に注目すべき点
- アサーションエラーの詳細
- テストデータの準備状況
- 非同期処理のタイミング問題
- 外部依存関係のモック状況

{context}"""

    def _get_assertion_template(self) -> str:
        """アサーション失敗専用プロンプトテンプレート"""
        return """アサーション失敗の詳細分析を行います：

## アサーション分析の観点
1. **期待値vs実際値**: 具体的な差異の分析
2. **データフロー**: 値がどのように変化したか
3. **ロジック**: 期待値設定の妥当性
4. **タイミング**: 非同期処理の影響

## 分析のポイント
- 期待値と実際値の具体的な差異
- 値の変化過程の追跡
- アサーション条件の妥当性
- テストケースの設計の適切性

{context}"""

    def _get_timeout_template(self) -> str:
        """タイムアウト専用プロンプトテンプレート"""
        return """タイムアウトエラーの専門分析を行います：

## タイムアウト分析の観点
1. **処理時間**: どの処理で時間がかかっているか
2. **リソース**: CPU、メモリ、ネットワークの状況
3. **設定**: タイムアウト設定の適切性
4. **最適化**: パフォーマンス改善の可能性

## 特に注目すべき点
- 長時間実行されている処理の特定
- リソース使用量の分析
- ネットワーク接続の問題
- 並列処理の効率性

{context}"""

    def _get_error_template(self) -> str:
        """一般エラー専用プロンプトテンプレート"""
        return """一般的なエラーの包括的分析を行います：

## エラー分析の観点
1. **エラーメッセージ**: 具体的なエラー内容
2. **スタックトレース**: エラー発生箇所の特定
3. **コンテキスト**: エラー発生時の状況
4. **関連要因**: 関連する設定や環境

## 分析のアプローチ
- エラーメッセージの詳細解析
- スタックトレースからの原因特定
- 関連するログエントリの調査
- 環境や設定の影響評価

{context}"""

    def _load_templates_from_file(self, config_path: Path) -> None:
        """ファイルからカスタムテンプレートを読み込み

        Args:
            config_path: テンプレートファイルのパス
        """
        try:
            # 簡単な実装 - 実際にはTOMLやYAMLパーサーを使用
            with open(config_path, encoding="utf-8") as f:
                f.read()
                # 基本的なテンプレート抽出（実装を簡略化）
                # 実際にはより堅牢なパーサーが必要
                pass
        except Exception as e:
            raise ConfigurationError(f"テンプレートファイルの読み込みに失敗しました: {e}")

    def get_analysis_prompt(self, error_type: FailureType | None = None, context: str = "") -> str:
        """エラータイプに応じた分析プロンプトを生成

        Args:
            error_type: エラータイプ
            context: 分析対象のコンテキスト

        Returns:
            生成されたプロンプト
        """
        # エラータイプ別の専用テンプレートがある場合は使用
        if error_type and error_type.value in self.templates.get("error_specific", {}):
            template = self.templates["error_specific"][error_type.value]
        else:
            template = self.templates["analysis"]

        # カスタムテンプレートがある場合は優先
        if "analysis" in self.custom_templates:
            template = self.custom_templates["analysis"]

        return self._substitute_variables(template, {"context": context})

    def get_fix_prompt(self, analysis_result: AnalysisResult, context: str = "") -> str:
        """修正提案用プロンプトを生成

        Args:
            analysis_result: 分析結果
            context: 元のコンテキスト

        Returns:
            修正提案用プロンプト
        """
        template = self.custom_templates.get("fix_suggestion", self.templates["fix_suggestion"])

        return self._substitute_variables(template, {"analysis_result": analysis_result.summary, "context": context})

    def get_interactive_prompt(self, conversation_history: list[str], context: str = "") -> str:
        """対話用プロンプトを生成

        Args:
            conversation_history: 会話履歴
            context: 現在のコンテキスト

        Returns:
            対話用プロンプト
        """
        template = self.custom_templates.get("interactive", self.templates["interactive"])

        history_text = "\n".join(conversation_history) if conversation_history else "（まだ会話はありません）"

        return self._substitute_variables(template, {"conversation_history": history_text, "context": context})

    def add_custom_prompt(self, name: str, template: str) -> None:
        """カスタムプロンプトを追加

        Args:
            name: プロンプト名
            template: プロンプトテンプレート
        """
        self.custom_templates[name] = template

    def get_custom_prompt(self, name: str, variables: dict[str, str] | None = None) -> str:
        """カスタムプロンプトを取得

        Args:
            name: プロンプト名
            variables: 置換変数

        Returns:
            生成されたプロンプト

        Raises:
            ConfigurationError: プロンプトが見つからない場合
        """
        if name not in self.custom_templates:
            raise ConfigurationError(f"カスタムプロンプト '{name}' が見つかりません")

        template = self.custom_templates[name]
        return self._substitute_variables(template, variables or {})

    def list_available_templates(self) -> list[str]:
        """利用可能なテンプレート一覧を取得

        Returns:
            テンプレート名のリスト
        """
        templates = list(self.templates.keys())
        templates.extend(self.custom_templates.keys())
        return sorted(set(templates))

    def _substitute_variables(self, template: str, variables: dict[str, str]) -> str:
        """テンプレート内の変数を置換

        Args:
            template: テンプレート文字列
            variables: 置換変数の辞書

        Returns:
            変数が置換されたテンプレート
        """
        result = template
        for key, value in variables.items():
            # {key} 形式の変数を置換
            result = result.replace(f"{{{key}}}", str(value))

        return result

    def validate_template(self, template: str) -> list[str]:
        """テンプレートの妥当性を検証

        Args:
            template: 検証するテンプレート

        Returns:
            検証エラーのリスト（空の場合は問題なし）
        """
        errors = []

        # 基本的な検証
        if not template.strip():
            errors.append("テンプレートが空です")

        # 変数の形式チェック
        variables = re.findall(r"\{(\w+)\}", template)
        for var in variables:
            if not var.isidentifier():
                errors.append(f"無効な変数名: {var}")

        return errors

    def get_template_variables(self, template: str) -> list[str]:
        """テンプレートで使用されている変数一覧を取得

        Args:
            template: テンプレート文字列

        Returns:
            変数名のリスト
        """
        return re.findall(r"\{(\w+)\}", template)

    def create_prompt_from_error_context(
        self,
        error_type: FailureType,
        error_message: str,
        file_path: str | None = None,
        line_number: int | None = None,
        stack_trace: str | None = None,
    ) -> str:
        """エラーコンテキストから専用プロンプトを作成

        Args:
            error_type: エラータイプ
            error_message: エラーメッセージ
            file_path: ファイルパス
            line_number: 行番号
            stack_trace: スタックトレース

        Returns:
            生成されたプロンプト
        """
        context_parts = [f"エラーメッセージ: {error_message}"]

        if file_path:
            location = f"ファイル: {file_path}"
            if line_number:
                location += f" (行 {line_number})"
            context_parts.append(location)

        if stack_trace:
            context_parts.append(f"スタックトレース:\n{stack_trace}")

        context = "\n".join(context_parts)
        return self.get_analysis_prompt(error_type, context)
