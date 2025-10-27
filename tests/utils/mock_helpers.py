"""
テスト用のモックヘルパー関数

Rich Promptモッキングなどの共通的なモック設定を提供します。
"""

from collections.abc import Iterator
from typing import Any
from unittest.mock import Mock


class InfiniteIterator:
    """無限に値を返すイテレータ

    指定された値のリストを順番に返し、リストが終わったら最後の値を無限に返します。
    StopIterationエラーを防ぐために使用します。
    """

    def __init__(self, values: list[Any], fallback: Any = "q"):
        """初期化

        Args:
            values: 返す値のリスト
            fallback: リストが終わった後に返すフォールバック値
        """
        self.values = values
        self.fallback = fallback
        self.index = 0

    def __iter__(self) -> Iterator[Any]:
        return self

    def __next__(self) -> Any:
        if self.index < len(self.values):
            value = self.values[self.index]
            self.index += 1
            return value
        else:
            return self.fallback


def create_prompt_side_effect(values: list[Any], fallback: Any = "q") -> InfiniteIterator:
    """Rich Prompt用のside_effectを作成

    Args:
        values: 返す値のリスト
        fallback: リストが終わった後に返すフォールバック値（デフォルト: "q"）

    Returns:
        StopIterationを発生させない無限イテレータ
    """
    return InfiniteIterator(values, fallback)


def setup_stable_prompt_mock(mock_prompt: Mock, values: list[Any], fallback: Any = "q") -> None:
    """Rich Promptモックを安定化

    Args:
        mock_prompt: モックオブジェクト
        values: 返す値のリスト
        fallback: リストが終わった後に返すフォールバック値
    """
    mock_prompt.side_effect = create_prompt_side_effect(values, fallback)


def create_stable_mock_with_values(values: list[Any], fallback: Any = "q") -> Mock:
    """安定したモックオブジェクトを作成

    Args:
        values: 返す値のリスト
        fallback: リストが終わった後に返すフォールバック値

    Returns:
        設定済みのモックオブジェクト
    """
    mock = Mock()
    setup_stable_prompt_mock(mock, values, fallback)
    return mock
