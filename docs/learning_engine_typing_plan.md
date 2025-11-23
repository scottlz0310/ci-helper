# Learning Engine Typing Cleanup Plan

## 現状の課題
- `UnknownErrorPayload` と `PotentialPatternPayload` を導入したが、関数シグネチャが `dict[str, Any]` のまま残っている箇所が多く、TypedDict との不整合でエラーが発生している。
- `UpdateStats` を返す関数 (`update_pattern_database_dynamically`) の戻り値型が `dict[str, Any]` のままで、pyright がエラーを報告している。
- 潜在パターン (`potential_patterns.json`) の JSON 構造に必須キー/任意キーが入り混じっており、TypedDict の `total=False` を使う場合にキー存在チェックを明示する必要がある。
- `_get_frequent_unknown_errors` や `_find_similar_unknown_error` が `list[dict[str, Any]]` を受け取る設計のままで、TypedDict を渡すと不整合が発生する。

## 解決方針
1. **TypedDict の階層化**
   - `UnknownErrorPayload` は未知エラー共有フィールドのみを保持し、潜在パターン専用の `PotentialPatternPayload(UnknownErrorPayload)` を追加。
   - `potential_patterns.json` 読み込み時は `list[PotentialPatternPayload]` として扱い、キーアクセス前に `get` で存在確認を行う。

2. **関数シグネチャの更新**
   - `_find_similar_unknown_error`, `_get_frequent_unknown_errors`, `_create_potential_pattern`, `promote_potential_pattern_to_official` など TypedDict を渡す/返す関数をすべて `UnknownErrorPayload` / `PotentialPatternPayload` を受け取るよう更新する。
   - `update_pattern_database_dynamically` の戻り値型を `UpdateStats` に変更し、呼び出し側 (`async clean` 等) も `UpdateStats` 扱いに置き換える。

3. **キー存在確認の明示**
   - TypedDict で任意キーにアクセスする際は `pattern_data.get("id")` のように `get` を使用し、`None` チェックを挟む。
   - `category_counts.most_common()` から返るリストは `list[tuple[str, int]]` なので、統計情報では `Sequence[tuple[str, int]]` を返すか、`list[str]` ではなく `list[tuple[str, int]]` を受け入れる構造に変更する。

4. **共通化/補助関数**
   - JSON 読み込み→ TypedDict 正規化を行う `_load_unknown_errors()` 補助関数を用意して、`process_unknown_error` や `get_unknown_error_statistics` から共通化する。
   - 同様に `potential_patterns.json` を扱う `_load_potential_patterns()` 補助関数を定義すると TypedDict 変換が明確になる。

5. **不要な isinstance の削除**
   - `process_feedback_for_pattern` 内の `isinstance(feedback_result, UserFeedback)` は不要なので削除し、`_normalize_feedback_results` を活用する。

この方針でコード整理を進めれば、learning_engine 周りの型エラーを段階的に解消できます。
