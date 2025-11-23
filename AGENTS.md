# Repository Guidelines

## Project Structure & Module Organization
Runtime code sits in `src/ci_helper`: `commands` holds CLI entrypoints, `core` orchestrates workflow execution, while `ai`, `formatters`, `config`, `utils`, and `ui` supply analysis, rendering, and IO helpers. Shared templates and docs live in `data/`, `templates/`, and `docs/`. Tests mirror the tree inside `tests/unit`, `tests/integration`, `tests/plugins`, plus reusable fixtures under `tests/fixtures`. Generated logs and coverage land in `logs/`, `formatted_logs/`, and `htmlcov/`; sweep them with `ci-run clean` before benchmarking.

## Build, Test & Development Commands
Install deps via `uv sync`, then confirm the CLI with `uv run python -m ci_helper.cli --help`. Typical loops: `uv run ci-run test --workflow sample.yml` drives local `act` executions, `uv run pytest` covers the suite, and `uv run pytest tests/unit -k pattern` narrows a repro. Run `uv run ruff check src tests` for linting, `uv run ruff format` for auto-formatting, and `uv run basedpyright` to uphold strict typing. Launch `run_tests_safe.sh` when you need Docker-parity with CI.

## Coding Style & Naming Conventions
Python 3.12+ syntax, four-space indentation, and a 120-column limit are enforced by Ruff, which also standardizes double quotes and import order. Treat type hints as mandatory, especially for CLI surfaces and hooks that cross process boundaries, and keep subprocess interactions wrapped in the hardened helpers under `ci_helper.utils`. Modules, functions, and fixtures follow snake_case; reserve CamelCase for classes and Pytest `Test*` containers.

## Communication
リポジトリに関する質問やステータス共有は、日本語で応答してください。

## Testing Guidelines
Pytest discovers `test_*.py`, `Test*` classes, and `test_*` functions. Keep fast behavioral checks in `tests/unit`, filesystem or `act` flows inside `tests/integration`, and workflow-driven plugin checks inside `tests/plugins`. Coverage must remain ≥70% (per `pyproject.toml`); review `htmlcov/index.html` and stash any interesting failure logs under `logs/` for reviewers. Stretch fixtures live in `tests/fixtures`; extend them whenever a scenario needs seeded logs, workflows, or config samples.

## Commit & Pull Request Guidelines
The history favors Conventional Commit prefixes (`fix:`, `feat:`, `chore:` with optional scopes). Summaries stay imperative, reference issues via `Fixes #123`, and describe failure modes plus repro steps in the body. Before opening a PR, run Ruff (lint + format), BasedPyright, the relevant Pytest targets, and capture `ci-run test --diff` output. PR descriptions should call out touched workflows, config changes (`ci-helper.toml`, `.actrc`, `.env`), and include screenshots only when Rich UI output changes. Close with a checklist noting lint, tests, and `uv run ci-run secrets check` results.
