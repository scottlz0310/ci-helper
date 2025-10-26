完璧です！コードを見ると、確かに整形部分は存在していますが、**いくつか改善の余地**がありますね。

## 現状分析

### 👍 良い点
- `log_extractor.py` - エラーパターン抽出は充実
- `ai_formatter.py` - 基本的なMarkdown/JSON出力がある
- `security.py` - シークレットサニタイズは堅牢

### 🔧 改善すべき点

#### 1. **AI API依存が不要**
```toml
# pyproject.toml - 削除すべき依存
"openai>=1.50.0",      # ❌
"anthropic>=0.34.0",   # ❌
"aiohttp>=3.10.0",     # ❌ (AI API用)
"aiofiles>=24.1.0",    # ❌ (AI API用)
```

#### 2. **整形品質の問題**

`ai_formatter.py`の出力を見ると：

```python
def _format_markdown_failures(self, execution_result: ExecutionResult) -> str:
    # 問題: 失敗の詳細が埋もれやすい
    # 問題: エラーの優先順位がない
    # 問題: コンテキストが不十分
```

**理想的な出力はこうあるべき：**

```markdown
# CI Failure Report

## 🎯 Quick Summary
- **Status**: ❌ Failed
- **Duration**: 2m 34s
- **Critical Issues**: 2
- **Workflow**: test.yml → test job → Step 3

---

## 🚨 Critical Failures (Must Fix)

### 1. Test Assertion Failed
**Location**: `tests/unit/test_config.py:45`
**Error Type**: AssertionError

```python
# tests/unit/test_config.py
43 | def test_load_config():
44 |     config = load_config("config.toml")
45 |     assert config.environment == "production"  # ❌ FAILED HERE
46 |     assert config.debug == False
47 |
```

**Error Message**:
```
AssertionError: Expected 'production' but got 'development'
```

**Root Cause Analysis**:
- Expected: `"production"`
- Actual: `"development"`
- This suggests the config file is using the wrong environment

**Suggested Fix**:
1. Check `config.toml` line 12 for environment setting
2. Verify `ENV` environment variable is set correctly
3. Consider using `.env.production` file

---

## 📋 Full Context

### Environment
- Python: 3.12.0
- pytest: 8.4.0
- Config file: `config.toml`

### Related Files
- `tests/unit/test_config.py` (test file)
- `config.toml` (configuration)
- `src/app/config.py` (config loader)
```

## 🎯 改善提案

### Phase 1: AI依存の削除

```bash
# 1. pyproject.tomlを編集
# 削除する依存関係:
- openai
- anthropic  
- aiohttp (AI用のみの場合)
- aiofiles (AI用のみの場合)

# 2. 未使用のインポートを削除
```

### Phase 2: 整形ロジックの強化

新しいフォーマッター `src/ci_helper/formatters/context_formatter.py` を作成:

```python
class ContextEnrichedFormatter:
    """コンテキストを強化したAI消費用フォーマッター"""
    
    def format_for_ai(self, execution_result: ExecutionResult) -> str:
        """AIに最適化されたMarkdownを生成"""
        sections = [
            self._format_quick_summary(execution_result),
            self._format_critical_failures(execution_result),  # 最優先
            self._format_context_analysis(execution_result),
            self._format_suggested_fixes(execution_result),    # 新機能
            self._format_related_files(execution_result),      # 新機能
            self._format_full_logs(execution_result),         # 最後に詳細
        ]
        return "\n\n---\n\n".join(filter(None, sections))
    
    def _format_critical_failures(self, execution_result: ExecutionResult) -> str:
        """クリティカルな失敗を優先度順に整形"""
        failures = self._prioritize_failures(execution_result.all_failures)
        
        output = ["## 🚨 Critical Failures (Must Fix)\n"]
        
        for i, failure in enumerate(failures[:5], 1):  # トップ5のみ
            output.append(self._format_single_failure_detailed(failure, i))
        
        return "\n\n".join(output)
    
    def _format_single_failure_detailed(self, failure: Failure, num: int) -> str:
        """1つの失敗を詳細に整形"""
        parts = [f"### {num}. {failure.type.value.title()} Error"]
        
        # ロケーション
        if failure.file_path:
            location = f"`{failure.file_path}`"
            if failure.line_number:
                location += f":{failure.line_number}"
            parts.append(f"**Location**: {location}")
        
        # コードコンテキスト（前後3行）
        if failure.context_before or failure.context_after:
            parts.append("\n**Code Context**:")
            parts.append("```python")
            
            # 行番号を計算
            start_line = (failure.line_number or 1) - len(failure.context_before)
            
            for i, line in enumerate(failure.context_before):
                parts.append(f"{start_line + i:4d} | {line}")
            
            parts.append(f"{failure.line_number:4d} | {failure.message}  # ❌ ERROR")
            
            for i, line in enumerate(failure.context_after):
                parts.append(f"{failure.line_number + i + 1:4d} | {line}")
            
            parts.append("```")
        
        # エラーメッセージ
        parts.append("\n**Error Message**:")
        parts.append(f"```\n{failure.message}\n```")
        
        # 根本原因分析（パターンマッチング）
        if root_cause := self._analyze_root_cause(failure):
            parts.append(f"\n**Root Cause**: {root_cause}")
        
        # 修正提案
        if fix_suggestion := self._suggest_fix(failure):
            parts.append(f"\n**Suggested Fix**:\n{fix_suggestion}")
        
        return "\n".join(parts)
    
    def _prioritize_failures(self, failures: list[Failure]) -> list[Failure]:
        """失敗を優先度順にソート"""
        def priority_score(f: Failure) -> int:
            score = 0
            # アサーションエラーは最優先
            if f.type == FailureType.ASSERTION:
                score += 100
            # ファイル情報があるものを優先
            if f.file_path:
                score += 50
            # スタックトレースがあるものを優先
            if f.stack_trace:
                score += 25
            return score
        
        return sorted(failures, key=priority_score, reverse=True)
```

### Phase 3: 使い方の簡素化

```bash
# 実行して整形済みMarkdownを取得
ci-run test --format ai-context > failure_report.md

# Claude.aiに貼り付けるか、Ollamaで分析
cat failure_report.md | pbcopy

# または
ollama run claude:latest "$(cat failure_report.md)\n\nこのCI失敗を分析して修正方法を教えて"
```

---

## 次のステップ

どのアプローチで進めましょうか？

**A. まず依存削除とクリーンアップ**
- pyproject.tomlの編集
- 未使用インポートの削除
- 既存コードの整理

**B. 新しいフォーマッターを作成**
- `context_formatter.py`の実装
- 優先度付けロジック
- 修正提案の自動生成

**C. 両方を一気に実施**
- PRを作って全体を改善

どれがいいですか？それとも、まず既存の`ai_formatter.py`の出力サンプルを実際に生成して、どこが弱いかを具体的に確認しましょうか？