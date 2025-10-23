# 技術詳細仕様

## 現状分析

### 実装済み機能
- ✅ AI統合アーキテクチャ（完全実装）
- ✅ 複数プロバイダー対応（OpenAI、Anthropic、Local）
- ✅ コスト管理機能（$0.31の使用実績あり）
- ✅ キャッシュ機能
- ✅ 設定管理システム
- ✅ エラーハンドリング

### 問題のある機能
- ❌ 環境検証が厳しすぎる（全プロバイダーのAPIキーを要求）
- ❌ ローカルLLMプロバイダーの初期化エラー
- ❌ 実用的な分析結果の不足

## 改善提案

### 1. 環境検証の緩和

**現在の問題**:
```python
# 全プロバイダーのAPIキーをチェック
for provider in available_providers:
    if provider != "local":
        api_key = config.get_ai_provider_api_key(provider)
        if not api_key:
            issues.append(f"{provider}のAPIキーが設定されていません")
```

**改善案**:
```python
# 指定されたプロバイダーのみチェック
def validate_provider_only(provider_name: str):
    if provider_name == "local":
        return validate_ollama_connection()
    else:
        return validate_api_key(provider_name)
```

### 2. パターン認識エンジン

**実装例**:
```python
class PatternEngine:
    def __init__(self):
        self.patterns = {
            "setup_uv_permission": {
                "regex": r"permission denied.*hostedtoolcache",
                "solution_template": "actrc_privileged",
                "confidence": 0.95
            },
            "docker_pull_timeout": {
                "regex": r"timeout.*docker pull",
                "solution_template": "docker_timeout_fix",
                "confidence": 0.85
            }
        }
    
    def detect(self, log_content: str) -> List[Pattern]:
        matches = []
        for name, pattern in self.patterns.items():
            if re.search(pattern["regex"], log_content, re.IGNORECASE):
                matches.append(Pattern(
                    name=name,
                    confidence=pattern["confidence"],
                    solution=pattern["solution_template"]
                ))
        return matches
```

### 3. 修正提案システム

**テンプレート例**:
```json
{
  "actrc_privileged": {
    "title": "Act権限エラーの修正",
    "description": "setup-uvアクションの権限問題を解決",
    "steps": [
      ".actrcファイルに--privilegedフラグを追加",
      "Dockerコンテナに管理者権限を付与"
    ],
    "files": [".actrc"],
    "content": "--privileged\n",
    "risk": "low",
    "time_estimate": "2分",
    "auto_applicable": true
  }
}
```

### 4. 自動修正機能

**実装例**:
```python
class AutoFixer:
    def apply_fix(self, suggestion: FixSuggestion) -> FixResult:
        # 1. バックアップ作成
        backup_path = self.create_backup(suggestion.files)
        
        try:
            # 2. 修正適用
            for file_path in suggestion.files:
                self.apply_file_fix(file_path, suggestion)
            
            # 3. 検証
            if self.verify_fix(suggestion):
                return FixResult(success=True, backup=backup_path)
            else:
                self.rollback(backup_path)
                return FixResult(success=False, error="検証失敗")
                
        except Exception as e:
            self.rollback(backup_path)
            return FixResult(success=False, error=str(e))
```

## 実装ファイル構成

```
src/ci_helper/
├── ai/
│   ├── pattern_engine.py      # パターン認識エンジン
│   ├── fix_templates.py       # 修正テンプレート
│   ├── auto_fixer.py         # 自動修正機能
│   └── learning_engine.py    # 学習機能
├── data/
│   ├── patterns.json         # エラーパターンDB
│   └── fix_templates.json    # 修正テンプレートDB
└── commands/
    └── analyze.py            # 改善されたanalyzeコマンド
```

## テストケース

### パターン認識テスト
```python
def test_permission_pattern():
    log = "EACCES: permission denied, mkdir '/opt/hostedtoolcache/uv/0.9.5'"
    patterns = pattern_engine.detect(log)
    assert len(patterns) == 1
    assert patterns[0].name == "setup_uv_permission"
    assert patterns[0].confidence > 0.9
```

### 自動修正テスト
```python
def test_actrc_fix():
    suggestion = FixSuggestion(
        title="権限修正",
        files=[".actrc"],
        content="--privileged\n"
    )
    result = auto_fixer.apply_fix(suggestion)
    assert result.success
    assert Path(".actrc").read_text().strip() == "--privileged"
```

## 段階的実装アプローチ

### Week 1-2: パターン認識
1. 既存ログからパターン抽出
2. 正規表現ベースの検出器実装
3. 信頼度計算アルゴリズム

### Week 3-4: 修正提案
1. テンプレートシステム構築
2. ファイル解析機能
3. 影響範囲評価

### Week 5-6: 自動修正
1. ファイル更新機能
2. バックアップ・ロールバック
3. 修正検証機能

### Week 7-8: 学習・改善
1. フィードバック収集
2. パターン学習機能
3. 継続的改善システム

---

**この技術仕様により、実用的で信頼性の高いAI分析機能を実現できます。**