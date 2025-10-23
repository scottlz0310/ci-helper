"""
サンプルログデータ

このファイルは様々なCI/CD失敗パターンを模擬するログデータを提供します。
ログ解析機能のテストで使用され、実際のCI環境で発生するエラーパターンを再現します。
"""

# 基本的なテスト失敗ログ
BASIC_TEST_FAILURE_LOG = """
STEP: Run tests
npm test

> test-project@1.0.0 test
> jest

FAIL src/auth.test.js
  ✕ should authenticate user with valid credentials (25ms)
  ✕ should reject invalid credentials (15ms)

● should authenticate user with valid credentials

  expect(received).toBe(expected) // Object.is equality

  Expected: 200
  Received: 401

    at Object.<anonymous> (src/auth.test.js:15:23)

● should reject invalid credentials

  expect(received).toBe(expected) // Object.is equality

  Expected: 401
  Received: 200

    at Object.<anonymous> (src/auth.test.js:25:33)

Test Suites: 1 failed, 0 passed, 1 total
Tests:       2 failed, 0 passed, 2 total
Snapshots:   0 total
Time:        2.456 s
Ran all test suites.
"""

# ビルド失敗ログ
BUILD_FAILURE_LOG = """
STEP: Build application
npm run build

> test-project@1.0.0 build
> webpack --mode production

Hash: 1234567890abcdef
Version: webpack 5.88.0
Time: 1234ms
Built at: 2024-01-15 10:30:45

ERROR in ./src/main.js 15:0-25
Module not found: Error: Can't resolve './missing-module' in '/github/workspace/src'
 @ ./src/main.js 15:0-25

ERROR in ./src/utils.js 8:0-30
Module not found: Error: Can't resolve 'non-existent-package' in '/github/workspace/src'
 @ ./src/utils.js 8:0-30

webpack 5.88.0 compiled with 2 errors in 1234 ms
"""

# 依存関係エラーログ
DEPENDENCY_ERROR_LOG = """
STEP: Install dependencies
npm install

npm ERR! code ENOENT
npm ERR! syscall open
npm ERR! path /github/workspace/package.json
npm ERR! errno -2
npm ERR! enoent ENOENT: no such file or directory, open '/github/workspace/package.json'
npm ERR! enoent This is related to npm not being able to find a file.
npm ERR! enoent

npm ERR! A complete log of this run can be found in:
npm ERR!     /home/runner/.npm/_logs/2024-01-15T10_30_45_123Z-debug-0.log
"""

# データベース接続エラーログ
DATABASE_ERROR_LOG = """
STEP: Run integration tests
npm run test:integration

> test-project@1.0.0 test:integration
> jest --config jest.integration.config.js

FAIL tests/integration/database.test.js
  ✕ should connect to database (30000ms)
  ✕ should perform CRUD operations (5000ms)

● should connect to database

  TimeoutError: Database connection timed out after 30 seconds

    at Database.connect (src/database.js:45:15)
    at Object.<anonymous> (tests/integration/database.test.js:12:18)

● should perform CRUD operations

  Error: Connection not established

    at Database.query (src/database.js:78:11)
    at Object.<anonymous> (tests/integration/database.test.js:25:20)

Test Suites: 1 failed, 0 passed, 1 total
Tests:       2 failed, 0 passed, 2 total
"""

# 型チェックエラーログ
TYPE_CHECK_ERROR_LOG = """
STEP: Type checking
npm run type-check

> test-project@1.0.0 type-check
> tsc --noEmit

src/auth.ts:15:7 - error TS2322: Type 'string' is not assignable to type 'number'.

15   let userId: number = "invalid";
         ~~~~~~

src/utils.ts:23:16 - error TS2339: Property 'nonExistent' does not exist on type 'User'.

23   return user.nonExistent;
                  ~~~~~~~~~~~

src/api.ts:45:3 - error TS2345: Argument of type 'undefined' is not assignable to parameter of type 'string'.

45   processData(undefined);
     ~~~~~~~~~~~~~~~~~~~

Found 3 errors in 3 files.
"""

# リンターエラーログ
LINT_ERROR_LOG = """
STEP: Lint code
npm run lint

> test-project@1.0.0 lint
> eslint src/

/github/workspace/src/auth.js
  15:1   error    'console' is not defined                     no-undef
  23:15  error    Missing semicolon                           semi
  34:1   warning  Unexpected console statement                no-console
  45:20  error    'userName' is defined but never used       no-unused-vars

/github/workspace/src/utils.js
  8:1    error    Expected indentation of 2 spaces but found 4  indent
  12:25  error    Strings must use singlequote                   quotes
  18:1   error    More than 1 blank line not allowed            no-multiple-empty-lines

✖ 7 problems (6 errors, 1 warning)
  4 errors and 0 warnings potentially fixable with the --fix option.
"""

# Docker関連エラーログ
DOCKER_ERROR_LOG = """
STEP: Build Docker image
docker build -t test-app .

Sending build context to Docker daemon  15.36kB
Step 1/8 : FROM node:18-alpine
 ---> 1234567890ab
Step 2/8 : WORKDIR /app
 ---> Using cache
 ---> abcdef123456
Step 3/8 : COPY package*.json ./
COPY failed: file not found in build context or excluded by .dockerignore: stat package.json: file does not exist
"""

# セキュリティスキャンエラーログ
SECURITY_SCAN_ERROR_LOG = """
STEP: Security scan
npm audit

# npm audit report

lodash  <4.17.21
Severity: high
Prototype Pollution in lodash - https://github.com/advisories/GHSA-35jh-r3h4-6jhm
fix available via `npm audit fix --force`
Will install lodash@4.17.21, which is a breaking change
node_modules/lodash

express  <4.18.2
Severity: moderate
qs prototype poisoning - https://github.com/advisories/GHSA-hrpp-h998-j3pp
fix available via `npm audit fix`
node_modules/express

3 vulnerabilities (1 moderate, 2 high)

To address issues that do not require attention, run:
  npm audit fix

To address all issues (including breaking changes), run:
  npm audit fix --force
"""

# 複合エラーログ（複数の問題が同時発生）
COMPLEX_ERROR_LOG = """
STEP: Run full test suite
npm run test:all

> test-project@1.0.0 test:all
> npm run lint && npm run type-check && npm run test && npm run test:integration

> test-project@1.0.0 lint
> eslint src/

/github/workspace/src/auth.js
  15:1  error  'console' is not defined  no-undef

✖ 1 problem (1 error, 0 warning)

> test-project@1.0.0 type-check
> tsc --noEmit

src/auth.ts:15:7 - error TS2322: Type 'string' is not assignable to type 'number'.

Found 1 error in 1 file.

> test-project@1.0.0 test
> jest

FAIL src/auth.test.js
  ✕ should authenticate user (25ms)

● should authenticate user

  TypeError: Cannot read properties of undefined (reading 'token')

    at authenticate (src/auth.js:23:15)
    at Object.<anonymous> (src/auth.test.js:15:23)

Test Suites: 1 failed, 0 passed, 1 total
Tests:       1 failed, 0 passed, 1 total

> test-project@1.0.0 test:integration
> jest --config jest.integration.config.js

FAIL tests/integration/api.test.js
  ✕ should handle API requests (30000ms)

● should handle API requests

  TimeoutError: Request timed out after 30 seconds

    at ApiClient.request (src/api-client.js:45:15)
"""

# 大きなログファイル（パフォーマンステスト用）
LARGE_LOG_CONTENT = (
    """
STEP: Run extensive test suite
"""
    + "\n".join(
        [
            f"Running test {i}: {'PASS' if i % 10 != 0 else 'FAIL'} - Test case {i} completed in {i % 100}ms"
            for i in range(1, 1001)
        ]
    )
    + """

FAILURES:
"""
    + "\n".join(
        [f"test_case_{i}.py::test_function_{i} FAILED - AssertionError: Test {i} failed" for i in range(10, 101, 10)]
    )
    + """

Test Summary:
- Total tests: 1000
- Passed: 900
- Failed: 100
- Execution time: 45.6 seconds
"""
)

# 不正形式のログコンテンツ
MALFORMED_LOG_CONTENT = """
STEP: Invalid log format
This is not a proper log format
\x00\x01\x02 Binary data mixed in
Invalid UTF-8: \xff\xfe
Incomplete JSON: {"error": "missing
Random characters: ñáéíóú中文日本語
Mixed encodings and control characters
"""

# 空のログファイル
EMPTY_LOG_CONTENT = ""

# ログファイルのメタデータ
LOG_METADATA = {
    "basic_test_failure": {
        "description": "基本的なテスト失敗パターン",
        "error_types": ["test_failure", "assertion_error"],
        "severity": "medium",
        "estimated_fix_time": "15分",
    },
    "build_failure": {
        "description": "ビルド失敗パターン",
        "error_types": ["build_error", "module_not_found"],
        "severity": "high",
        "estimated_fix_time": "30分",
    },
    "dependency_error": {
        "description": "依存関係エラーパターン",
        "error_types": ["dependency_error", "file_not_found"],
        "severity": "high",
        "estimated_fix_time": "10分",
    },
    "database_error": {
        "description": "データベース接続エラーパターン",
        "error_types": ["database_error", "timeout_error"],
        "severity": "high",
        "estimated_fix_time": "45分",
    },
    "type_check_error": {
        "description": "型チェックエラーパターン",
        "error_types": ["type_error", "typescript_error"],
        "severity": "medium",
        "estimated_fix_time": "20分",
    },
    "lint_error": {
        "description": "リンターエラーパターン",
        "error_types": ["lint_error", "code_style"],
        "severity": "low",
        "estimated_fix_time": "10分",
    },
    "docker_error": {
        "description": "Dockerビルドエラーパターン",
        "error_types": ["docker_error", "build_context"],
        "severity": "medium",
        "estimated_fix_time": "25分",
    },
    "security_scan_error": {
        "description": "セキュリティスキャンエラーパターン",
        "error_types": ["security_vulnerability", "dependency_audit"],
        "severity": "high",
        "estimated_fix_time": "60分",
    },
}


def get_log_by_type(log_type: str) -> str:
    """
    ログタイプに基づいてサンプルログを取得

    Args:
        log_type: ログのタイプ

    Returns:
        str: 対応するログコンテンツ
    """
    log_map = {
        "basic_test_failure": BASIC_TEST_FAILURE_LOG,
        "build_failure": BUILD_FAILURE_LOG,
        "dependency_error": DEPENDENCY_ERROR_LOG,
        "database_error": DATABASE_ERROR_LOG,
        "type_check_error": TYPE_CHECK_ERROR_LOG,
        "lint_error": LINT_ERROR_LOG,
        "docker_error": DOCKER_ERROR_LOG,
        "security_scan_error": SECURITY_SCAN_ERROR_LOG,
        "complex_error": COMPLEX_ERROR_LOG,
        "large_log": LARGE_LOG_CONTENT,
        "malformed_log": MALFORMED_LOG_CONTENT,
        "empty_log": EMPTY_LOG_CONTENT,
    }

    return log_map.get(log_type, BASIC_TEST_FAILURE_LOG)


def create_custom_log(
    step_name: str, error_message: str, error_type: str = "generic_error", additional_context: str = ""
) -> str:
    """
    カスタムログコンテンツを作成

    Args:
        step_name: ステップ名
        error_message: エラーメッセージ
        error_type: エラータイプ
        additional_context: 追加のコンテキスト情報

    Returns:
        str: 生成されたログコンテンツ
    """
    log_content = f"""
STEP: {step_name}

{error_message}

Error Type: {error_type}
"""

    if additional_context:
        log_content += f"\nAdditional Context:\n{additional_context}"

    return log_content.strip()
