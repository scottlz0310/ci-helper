"""
pytest設定と共有フィクスチャ
"""

from collections.abc import Generator
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from ci_helper.utils.config import Config


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """一時ディレクトリを提供するフィクスチャ"""
    with TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def sample_config(temp_dir: Path) -> Config:
    """テスト用の設定を提供するフィクスチャ"""
    return Config(project_root=temp_dir)


@pytest.fixture
def sample_workflow_dir(temp_dir: Path) -> Path:
    """サンプルワークフローディレクトリを作成するフィクスチャ"""
    workflow_dir = temp_dir / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)

    # サンプルワークフローファイルを作成
    sample_workflow = workflow_dir / "test.yml"
    sample_workflow.write_text("""
name: Test
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run tests
        run: echo "Running tests"
""")

    return workflow_dir
