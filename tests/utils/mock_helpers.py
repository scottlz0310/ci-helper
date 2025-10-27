"""
テスト用のモックヘルパー関数

Rich Promptモッキングなどの共通的なモック設定を提供します。
非同期モックの安定化機能も含みます。
"""

import asyncio
from collections.abc import Callable, Iterator
from typing import Any
from unittest.mock import AsyncMock, Mock


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


# 非同期モック管理機能


class AsyncMockManager:
    """非同期モックの管理と安定化を担当するクラス"""

    @staticmethod
    def create_async_mock_with_return_value(return_value: Any) -> AsyncMock:
        """戻り値を持つAsyncMockを作成

        Args:
            return_value: 非同期関数が返すべき値

        Returns:
            設定済みのAsyncMock
        """
        async_mock = AsyncMock()
        async_mock.return_value = return_value
        return async_mock

    @staticmethod
    def create_async_mock_with_side_effect(side_effect: Exception | list[Any] | Callable) -> AsyncMock:
        """side_effectを持つAsyncMockを作成

        Args:
            side_effect: 例外、値のリスト、または呼び出し可能オブジェクト

        Returns:
            設定済みのAsyncMock
        """
        async_mock = AsyncMock()
        if isinstance(side_effect, Exception):
            async_mock.side_effect = side_effect
        elif isinstance(side_effect, list):
            # リストの場合は順番に値を返すように設定
            async_mock.side_effect = side_effect
        elif callable(side_effect):
            async_mock.side_effect = side_effect
        else:
            async_mock.side_effect = side_effect
        return async_mock

    @staticmethod
    def create_async_iterator_mock(values: list[Any]) -> AsyncMock:
        """非同期イテレータのモックを作成

        Args:
            values: イテレータが返すべき値のリスト

        Returns:
            非同期イテレータとして動作するAsyncMock
        """

        async def async_generator():
            for value in values:
                yield value

        mock = AsyncMock()
        mock.return_value = async_generator()
        return mock

    @staticmethod
    def setup_async_context_manager(mock_obj: AsyncMock, return_value: Any = None) -> AsyncMock:
        """非同期コンテキストマネージャーとして動作するモックを設定

        Args:
            mock_obj: 設定するAsyncMockオブジェクト
            return_value: __aenter__が返すべき値

        Returns:
            設定済みのAsyncMock
        """
        mock_obj.__aenter__ = AsyncMock(return_value=return_value or mock_obj)
        mock_obj.__aexit__ = AsyncMock(return_value=None)
        return mock_obj

    @staticmethod
    def create_coroutine_mock(return_value: Any = None) -> Mock:
        """コルーチンを返すモックを作成

        Args:
            return_value: コルーチンが返すべき値

        Returns:
            コルーチンを返すMock
        """

        async def mock_coroutine():
            return return_value

        mock = Mock()
        mock.return_value = mock_coroutine()
        return mock


class AsyncMockStabilizer:
    """非同期モックの安定性を確保するためのユーティリティ"""

    @staticmethod
    def fix_async_mock_side_effects(mock_obj: AsyncMock, values: list[Any]) -> None:
        """AsyncMockのside_effectを安定化

        StopIterationエラーを防ぐために、値のリストを無限に繰り返すように設定

        Args:
            mock_obj: 修正するAsyncMockオブジェクト
            values: 返すべき値のリスト
        """
        if not values:
            values = [None]

        async def infinite_side_effect(*args, **kwargs):
            # 値を順番に返し、最後まで行ったら最後の値を繰り返す
            index = getattr(infinite_side_effect, "_index", 0)
            if index < len(values):
                result = values[index]
                infinite_side_effect._index = index + 1
            else:
                result = values[-1]  # 最後の値を繰り返す

            return result

        infinite_side_effect._index = 0
        mock_obj.side_effect = infinite_side_effect

    @staticmethod
    def ensure_async_mock_cleanup(mock_obj: AsyncMock) -> None:
        """AsyncMockのクリーンアップを確保

        Args:
            mock_obj: クリーンアップするAsyncMockオブジェクト
        """
        # 未完了のコルーチンがあれば適切にクリーンアップ
        if hasattr(mock_obj, "_mock_return_value"):
            return_value = mock_obj._mock_return_value
            if asyncio.iscoroutine(return_value):
                try:
                    return_value.close()
                except (RuntimeError, StopIteration):
                    pass  # 既にクローズされている場合は無視

    @staticmethod
    def create_stable_async_stream(chunks: list[str]) -> AsyncMock:
        """安定した非同期ストリームモックを作成

        Args:
            chunks: ストリームで返すべきチャンクのリスト

        Returns:
            安定した非同期ストリームモック
        """

        async def mock_stream():
            for chunk in chunks:
                yield chunk

        mock = AsyncMock()
        mock.return_value = mock_stream()
        return mock


def setup_stable_async_mock(mock_obj: AsyncMock, return_value: Any = None, side_effect: Any = None) -> AsyncMock:
    """非同期モックを安定化して設定

    Args:
        mock_obj: 設定するAsyncMockオブジェクト
        return_value: 戻り値
        side_effect: サイドエフェクト

    Returns:
        設定済みのAsyncMock
    """
    if return_value is not None:
        mock_obj.return_value = return_value

    if side_effect is not None:
        if isinstance(side_effect, list):
            AsyncMockStabilizer.fix_async_mock_side_effects(mock_obj, side_effect)
        else:
            mock_obj.side_effect = side_effect

    return mock_obj


def create_async_mock_with_stable_behavior(
    return_value: Any = None, side_effect: Any = None, is_context_manager: bool = False
) -> AsyncMock:
    """安定した動作を持つAsyncMockを作成

    Args:
        return_value: 戻り値
        side_effect: サイドエフェクト
        is_context_manager: コンテキストマネージャーとして設定するか

    Returns:
        設定済みのAsyncMock
    """
    mock = AsyncMock()
    setup_stable_async_mock(mock, return_value, side_effect)

    if is_context_manager:
        AsyncMockManager.setup_async_context_manager(mock, mock)

    return mock


def patch_async_method_with_stable_mock(target_object: Any, method_name: str, **mock_kwargs) -> AsyncMock:
    """オブジェクトの非同期メソッドを安定したモックでパッチ

    Args:
        target_object: パッチするオブジェクト
        method_name: パッチするメソッド名
        **mock_kwargs: AsyncMockに渡すキーワード引数

    Returns:
        作成されたAsyncMock
    """
    mock = create_async_mock_with_stable_behavior(**mock_kwargs)
    setattr(target_object, method_name, mock)
    return mock


def setup_provider_mock_with_async_cleanup(provider_mock: Mock) -> Mock:
    """プロバイダーモックに非同期クリーンアップメソッドを追加

    Args:
        provider_mock: プロバイダーのモックオブジェクト

    Returns:
        非同期クリーンアップメソッドが追加されたモック
    """
    # cleanup メソッドを AsyncMock として設定
    provider_mock.cleanup = AsyncMock(return_value=None)

    # その他の一般的な非同期メソッドも設定
    provider_mock.validate_connection = AsyncMock(return_value=True)
    provider_mock.analyze = AsyncMock(return_value={})
    provider_mock.stream_analyze = AsyncMockManager.create_async_iterator_mock([])

    return provider_mock


def create_stable_provider_mock(**kwargs) -> Mock:
    """安定したプロバイダーモックを作成

    Args:
        **kwargs: プロバイダーモックに設定する追加属性

    Returns:
        設定済みのプロバイダーモック
    """
    provider_mock = Mock()
    setup_provider_mock_with_async_cleanup(provider_mock)

    # 追加属性を設定
    for key, value in kwargs.items():
        setattr(provider_mock, key, value)

    return provider_mock


def fix_integration_mock_for_async_cleanup(integration_mock: Mock) -> Mock:
    """AIIntegrationモックの非同期クリーンアップを修正

    Args:
        integration_mock: AIIntegrationのモックオブジェクト

    Returns:
        修正されたモック
    """
    # providersが辞書として動作するように設定
    if not hasattr(integration_mock, "providers"):
        integration_mock.providers = {}

    # 既存のプロバイダーモックに非同期クリーンアップを追加
    for provider_name, provider_mock in integration_mock.providers.items():
        if isinstance(provider_mock, Mock):
            setup_provider_mock_with_async_cleanup(provider_mock)

    # cleanup メソッド自体も AsyncMock として設定
    integration_mock.cleanup = AsyncMock(return_value=None)

    return integration_mock


# ファイル操作モック安定化機能


class FileOperationMockHelper:
    """ファイル操作モックのヘルパークラス

    テスト間でのファイル操作の一貫性を確保し、
    競合状態を防ぐためのユーティリティを提供します。
    """

    @staticmethod
    def create_stable_file_mock(file_content: str = "", file_exists: bool = True) -> Mock:
        """安定したファイルモックを作成

        Args:
            file_content: ファイルの内容
            file_exists: ファイルが存在するか

        Returns:
            Mock: 設定済みのファイルモック
        """
        mock_file = Mock()

        if file_exists:
            mock_file.exists.return_value = True
            mock_file.is_file.return_value = True
            mock_file.read_text.return_value = file_content
            mock_file.write_text = Mock()
            mock_file.unlink = Mock()
        else:
            mock_file.exists.return_value = False
            mock_file.is_file.return_value = False
            mock_file.read_text.side_effect = FileNotFoundError("File not found")
            mock_file.write_text = Mock()
            mock_file.unlink.side_effect = FileNotFoundError("File not found")

        # 共通メソッドの設定
        mock_file.mkdir = Mock()
        mock_file.parent.mkdir = Mock()
        mock_file.__str__ = Mock(return_value="/mock/path/file.txt")
        mock_file.__fspath__ = Mock(return_value="/mock/path/file.txt")

        return mock_file

    @staticmethod
    def create_stable_directory_mock(dir_exists: bool = True, files: list = None) -> Mock:
        """安定したディレクトリモックを作成

        Args:
            dir_exists: ディレクトリが存在するか
            files: ディレクトリ内のファイルリスト

        Returns:
            Mock: 設定済みのディレクトリモック
        """
        mock_dir = Mock()
        files = files or []

        if dir_exists:
            mock_dir.exists.return_value = True
            mock_dir.is_dir.return_value = True
            mock_dir.mkdir = Mock()
            mock_dir.rmdir = Mock()
            mock_dir.iterdir.return_value = [Mock() for _ in files]
        else:
            mock_dir.exists.return_value = False
            mock_dir.is_dir.return_value = False
            mock_dir.mkdir = Mock()
            mock_dir.rmdir.side_effect = FileNotFoundError("Directory not found")
            mock_dir.iterdir.side_effect = FileNotFoundError("Directory not found")

        mock_dir.__str__ = Mock(return_value="/mock/path/directory")
        mock_dir.__fspath__ = Mock(return_value="/mock/path/directory")

        return mock_dir

    @staticmethod
    def setup_consistent_pathlib_mocks(mock_path_class: Mock, files: dict = None, directories: set = None) -> None:
        """一貫したpathlibモックを設定

        Args:
            mock_path_class: モック化するPathクラス
            files: ファイルパスと内容の辞書
            directories: 存在するディレクトリのセット
        """
        files = files or {}
        directories = directories or set()

        def mock_path_init(path_str):
            mock_path = Mock()
            mock_path._path_str = str(path_str)

            # ファイル存在チェック
            mock_path.exists.return_value = mock_path._path_str in files or mock_path._path_str in directories

            # ファイル/ディレクトリ判定
            mock_path.is_file.return_value = mock_path._path_str in files
            mock_path.is_dir.return_value = mock_path._path_str in directories

            # ファイル操作
            if mock_path._path_str in files:
                mock_path.read_text.return_value = files[mock_path._path_str]
                mock_path.write_text = Mock()
                mock_path.unlink = Mock()
            else:
                mock_path.read_text.side_effect = FileNotFoundError("File not found")
                mock_path.write_text = Mock()
                mock_path.unlink.side_effect = FileNotFoundError("File not found")

            # ディレクトリ操作
            mock_path.mkdir = Mock()
            mock_path.rmdir = Mock()

            # パス操作
            mock_path.__str__ = Mock(return_value=mock_path._path_str)
            mock_path.__fspath__ = Mock(return_value=mock_path._path_str)
            mock_path.parent = Mock()
            mock_path.parent.mkdir = Mock()

            return mock_path

        mock_path_class.side_effect = mock_path_init

    @staticmethod
    def create_stable_open_mock(files: dict = None) -> Mock:
        """安定したopen関数モックを作成

        Args:
            files: ファイルパスと内容の辞書

        Returns:
            Mock: 設定済みのopen関数モック
        """
        files = files or {}

        def mock_open_func(file_path, mode="r", *args, **kwargs):
            path_str = str(file_path)

            if "r" in mode:
                if path_str not in files:
                    raise FileNotFoundError(f"No such file or directory: '{path_str}'")

                mock_file = Mock()
                mock_file.read.return_value = files[path_str]
                mock_file.readlines.return_value = files[path_str].splitlines(keepends=True)
                mock_file.__enter__.return_value = mock_file
                mock_file.__exit__.return_value = None
                return mock_file

            elif "w" in mode or "a" in mode:
                mock_file = Mock()
                written_content = []

                def write_func(content):
                    written_content.append(content)
                    files[path_str] = "".join(written_content)

                mock_file.write = write_func
                mock_file.flush = Mock()
                mock_file.__enter__.return_value = mock_file
                mock_file.__exit__.return_value = None
                return mock_file

            else:
                raise ValueError(f"Unsupported file mode: {mode}")

        return Mock(side_effect=mock_open_func)

    @staticmethod
    def create_stable_tempfile_mocks() -> dict:
        """安定したtempfileモックを作成

        Returns:
            dict: tempfileモック関数の辞書
        """
        temp_counter = 0

        def mock_mkdtemp(prefix="tmp"):
            nonlocal temp_counter
            temp_counter += 1
            return f"/mock/temp/{prefix}{temp_counter:04d}"

        def mock_named_temporary_file(*args, **kwargs):
            nonlocal temp_counter
            temp_counter += 1
            temp_path = f"/mock/temp/tmp{temp_counter:04d}.tmp"

            mock_file = Mock()
            mock_file.name = temp_path
            mock_file.write = Mock()
            mock_file.read = Mock(return_value="")
            mock_file.flush = Mock()
            mock_file.__enter__.return_value = mock_file
            mock_file.__exit__.return_value = None
            return mock_file

        def mock_temporary_directory(*args, **kwargs):
            nonlocal temp_counter
            temp_counter += 1
            temp_path = f"/mock/temp/tmpdir{temp_counter:04d}"

            mock_temp_dir = Mock()
            mock_temp_dir.name = temp_path
            mock_temp_dir.__enter__.return_value = temp_path
            mock_temp_dir.__exit__.return_value = None
            return mock_temp_dir

        return {
            "mkdtemp": Mock(side_effect=mock_mkdtemp),
            "NamedTemporaryFile": Mock(side_effect=mock_named_temporary_file),
            "TemporaryDirectory": Mock(side_effect=mock_temporary_directory),
        }


def setup_stable_file_operation_mocks(files: dict = None, directories: set = None) -> dict:
    """安定したファイル操作モックを一括設定

    Args:
        files: ファイルパスと内容の辞書
        directories: 存在するディレクトリのセット

    Returns:
        dict: 設定されたモックオブジェクトの辞書
    """
    files = files or {}
    directories = directories or set()

    helper = FileOperationMockHelper()

    # 各種モックを作成
    open_mock = helper.create_stable_open_mock(files)
    tempfile_mocks = helper.create_stable_tempfile_mocks()

    return {
        "open": open_mock,
        "tempfile_mocks": tempfile_mocks,
        "files": files,
        "directories": directories,
    }


def ensure_file_operation_consistency(test_func):
    """ファイル操作の一貫性を確保するデコレータ

    Args:
        test_func: テスト関数

    Returns:
        ラップされたテスト関数
    """

    def wrapper(*args, **kwargs):
        # ファイル操作モックを設定
        mocks = setup_stable_file_operation_mocks()

        with patch("builtins.open", mocks["open"]):
            with patch("tempfile.mkdtemp", mocks["tempfile_mocks"]["mkdtemp"]):
                with patch("tempfile.NamedTemporaryFile", mocks["tempfile_mocks"]["NamedTemporaryFile"]):
                    with patch("tempfile.TemporaryDirectory", mocks["tempfile_mocks"]["TemporaryDirectory"]):
                        return test_func(*args, **kwargs)

    return wrapper
