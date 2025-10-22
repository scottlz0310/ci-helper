"""
ファイルシステム操作のモック

このファイルはファイルシステム操作（読み書き、ディレクトリ作成等）のモックを提供します。
実際のファイルシステムに影響を与えずにファイル操作をテストできます。
"""

from pathlib import Path
from unittest.mock import Mock, mock_open, patch
from typing import Dict, Any, Optional
import tempfile
import shutil


class MockFileSystem:
    """
    ファイルシステムのモック実装
    
    メモリ上でファイルシステムの状態を管理し、
    実際のディスクI/Oを行わずにファイル操作をテストできます。
    """
    
    def __init__(self):
        self.files: Dict[str, str] = {}
        self.directories: set = set()
        
    def create_file(self, path: str, content: str = "") -> None:
        """ファイルを作成"""
        self.files[path] = content
        # 親ディレクトリも作成
        parent = str(Path(path).parent)
        if parent != ".":
            self.directories.add(parent)
            
    def create_directory(self, path: str) -> None:
        """ディレクトリを作成"""
        self.directories.add(path)
        
    def read_file(self, path: str) -> str:
        """ファイルを読み込み"""
        if path not in self.files:
            raise FileNotFoundError(f"File not found: {path}")
        return self.files[path]
        
    def write_file(self, path: str, content: str) -> None:
        """ファイルに書き込み"""
        self.create_file(path, content)
        
    def exists(self, path: str) -> bool:
        """パスが存在するかチェック"""
        return path in self.files or path in self.directories
        
    def is_file(self, path: str) -> bool:
        """ファイルかどうかチェック"""
        return path in self.files
        
    def is_directory(self, path: str) -> bool:
        """ディレクトリかどうかチェック"""
        return path in self.directories
        
    def list_directory(self, path: str) -> list:
        """ディレクトリの内容を一覧"""
        if not self.is_directory(path):
            raise NotADirectoryError(f"Not a directory: {path}")
            
        items = []
        for file_path in self.files:
            if str(Path(file_path).parent) == path:
                items.append(Path(file_path).name)
        for dir_path in self.directories:
            if str(Path(dir_path).parent) == path:
                items.append(Path(dir_path).name)
        return items
        
    def delete_file(self, path: str) -> None:
        """ファイルを削除"""
        if path in self.files:
            del self.files[path]
        else:
            raise FileNotFoundError(f"File not found: {path}")
            
    def delete_directory(self, path: str) -> None:
        """ディレクトリを削除"""
        if path in self.directories:
            self.directories.remove(path)
        else:
            raise FileNotFoundError(f"Directory not found: {path}")


def create_mock_file_system_with_logs(temp_dir: Path) -> Dict[str, Any]:
    """
    ログファイルを含むモックファイルシステムを作成
    
    Args:
        temp_dir: 一時ディレクトリのパス
        
    Returns:
        Dict[str, Any]: モックファイルシステムの情報
    """
    from tests.fixtures.sample_logs import get_log_by_type
    
    # ログディレクトリを作成
    logs_dir = temp_dir / ".ci-helper" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    
    # 各種ログファイルを作成
    log_files = {}
    log_types = [
        "basic_test_failure",
        "build_failure", 
        "dependency_error",
        "database_error",
        "type_check_error"
    ]
    
    for i, log_type in enumerate(log_types):
        log_file = logs_dir / f"act_2024011{i+1}_120000.log"
        log_content = get_log_by_type(log_type)
        log_file.write_text(log_content, encoding="utf-8")
        log_files[log_type] = log_file
    
    # キャッシュディレクトリを作成
    cache_dir = temp_dir / ".ci-helper" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    # 設定ファイルを作成
    config_file = temp_dir / "ci-helper.toml"
    config_content = """
[ai]
default_provider = "openai"
cache_enabled = true

[ai.providers.openai]
api_key = "sk-test-key"
default_model = "gpt-4o"
"""
    config_file.write_text(config_content, encoding="utf-8")
    
    return {
        "temp_dir": temp_dir,
        "logs_dir": logs_dir,
        "cache_dir": cache_dir,
        "config_file": config_file,
        "log_files": log_files
    }


def create_mock_project_structure(temp_dir: Path) -> Dict[str, Path]:
    """
    プロジェクト構造のモックを作成
    
    Args:
        temp_dir: 一時ディレクトリのパス
        
    Returns:
        Dict[str, Path]: 作成されたファイル・ディレクトリのパス
    """
    # GitHub Actionsワークフロー
    workflows_dir = temp_dir / ".github" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    
    test_workflow = workflows_dir / "test.yml"
    test_workflow.write_text("""
name: Test
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '18'
      - name: Install dependencies
        run: npm install
      - name: Run tests
        run: npm test
""", encoding="utf-8")
    
    # package.json
    package_json = temp_dir / "package.json"
    package_json.write_text("""{
  "name": "test-project",
  "version": "1.0.0",
  "scripts": {
    "test": "jest",
    "build": "webpack",
    "lint": "eslint src/"
  },
  "dependencies": {
    "express": "^4.18.0"
  },
  "devDependencies": {
    "jest": "^29.0.0",
    "eslint": "^8.0.0"
  }
}""", encoding="utf-8")
    
    # ソースファイル
    src_dir = temp_dir / "src"
    src_dir.mkdir(exist_ok=True)
    
    main_js = src_dir / "main.js"
    main_js.write_text("""
const express = require('express');
const app = express();

app.get('/', (req, res) => {
  res.json({ message: 'Hello World' });
});

module.exports = app;
""", encoding="utf-8")
    
    # テストファイル
    tests_dir = temp_dir / "tests"
    tests_dir.mkdir(exist_ok=True)
    
    test_file = tests_dir / "main.test.js"
    test_file.write_text("""
const app = require('../src/main');
const request = require('supertest');

describe('Main App', () => {
  test('should return hello world', async () => {
    const response = await request(app).get('/');
    expect(response.status).toBe(200);
    expect(response.body.message).toBe('Hello World');
  });
});
""", encoding="utf-8")
    
    return {
        "workflows_dir": workflows_dir,
        "test_workflow": test_workflow,
        "package_json": package_json,
        "src_dir": src_dir,
        "main_js": main_js,
        "tests_dir": tests_dir,
        "test_file": test_file
    }


class MockPathOperations:
    """
    Path操作のモック
    
    pathlib.Pathの操作をモック化し、
    実際のファイルシステムに影響を与えずにテストできます。
    """
    
    def __init__(self, mock_fs: MockFileSystem):
        self.mock_fs = mock_fs
        
    def mock_path_exists(self, path: Path) -> bool:
        """Path.exists()のモック"""
        return self.mock_fs.exists(str(path))
        
    def mock_path_is_file(self, path: Path) -> bool:
        """Path.is_file()のモック"""
        return self.mock_fs.is_file(str(path))
        
    def mock_path_is_dir(self, path: Path) -> bool:
        """Path.is_dir()のモック"""
        return self.mock_fs.is_directory(str(path))
        
    def mock_path_read_text(self, path: Path, encoding: str = "utf-8") -> str:
        """Path.read_text()のモック"""
        return self.mock_fs.read_file(str(path))
        
    def mock_path_write_text(self, path: Path, content: str, encoding: str = "utf-8") -> None:
        """Path.write_text()のモック"""
        self.mock_fs.write_file(str(path), content)
        
    def mock_path_mkdir(self, path: Path, parents: bool = False, exist_ok: bool = False) -> None:
        """Path.mkdir()のモック"""
        if parents:
            # 親ディレクトリも作成
            parent = path.parent
            if parent != path and not self.mock_fs.exists(str(parent)):
                self.mock_path_mkdir(parent, parents=True, exist_ok=True)
        
        if self.mock_fs.exists(str(path)) and not exist_ok:
            raise FileExistsError(f"Directory already exists: {path}")
        
        self.mock_fs.create_directory(str(path))


def patch_file_operations(mock_fs: MockFileSystem):
    """
    ファイル操作をモックでパッチ
    
    Args:
        mock_fs: モックファイルシステム
        
    Returns:
        context manager: パッチされたファイル操作
    """
    path_ops = MockPathOperations(mock_fs)
    
    return patch.multiple(
        'pathlib.Path',
        exists=path_ops.mock_path_exists,
        is_file=path_ops.mock_path_is_file,
        is_dir=path_ops.mock_path_is_dir,
        read_text=path_ops.mock_path_read_text,
        write_text=path_ops.mock_path_write_text,
        mkdir=path_ops.mock_path_mkdir
    )