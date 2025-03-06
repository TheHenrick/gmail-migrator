# Gmail Migrator Tests

This directory contains tests for the Gmail Migrator application.

## Test Structure

The tests are organized as follows:

- `tests/services/`: Unit tests for service modules
  - `tests/services/outlook/`: Tests for Outlook service modules
  - `tests/services/gmail/`: Tests for Gmail service modules
- `tests/api/`: Tests for API endpoints
  - `tests/api/routers/`: Tests for API routers
- `tests/integration/`: Integration tests that test multiple components together

## Running Tests

To run all tests:

```bash
pytest
```

To run specific test categories:

```bash
# Run only Outlook-related tests
pytest -m outlook

# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run tests with coverage report
pytest --cov=app --cov-report=term-missing
```

## Test Configuration

The test configuration is defined in the `[tool.pytest.ini_options]` section of the `pyproject.toml` file at the root of the project. It includes:

- Test discovery patterns
- Test markers for categorizing tests
- Default options for running tests

Using `pyproject.toml` for pytest configuration helps consolidate configuration files and is the recommended approach for Poetry projects.

## Test Fixtures

Common test fixtures are defined in `conftest.py`. These include:

- Mock Outlook client
- Mock Gmail client
- Mock authentication managers
- Other shared fixtures

## Writing Tests

When writing new tests:

1. Follow the existing directory structure
2. Use appropriate markers to categorize tests (unit, integration, outlook, gmail, auth, etc.)
3. Use fixtures from `conftest.py` when possible
4. Write both unit and integration tests for new features
