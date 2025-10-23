# カスタムパターンディレクトリ

このディレクトリには、ユーザー定義のカスタムパターンが格納されます。

## ファイル構造

- `user_patterns.json` - ユーザーが手動で作成したパターン
- `learned_patterns.json` - 学習エンジンが自動生成したパターン
- `project_specific_patterns.json` - プロジェクト固有のパターン

## パターンの作成方法

カスタムパターンを作成する場合は、以下の形式に従ってください：

```json
{
    "patterns": [
        {
            "id": "custom_pattern_id",
            "name": "カスタムパターン名",
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
                "コンテキスト要件1",
                "コンテキスト要件2"
            ],
            "confidence_base": 0.8,
            "success_rate": 0.7,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "user_defined": true,
            "auto_generated": false,
            "source": "user",
            "occurrence_count": 0
        }
    ]
}
```

## 注意事項

- パターンIDは一意である必要があります
- 正規表現は適切にエスケープしてください
- 信頼度は0.0-1.0の範囲で設定してください
- カスタムパターンは組み込みパターンよりも優先されます
