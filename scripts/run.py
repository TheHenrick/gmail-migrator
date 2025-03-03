#!/usr/bin/env python3
"""
Helper script for common project tasks.

This script provides convenient commands for development tasks like running
the server, running tests, and formatting code.
"""

import os
import subprocess
import sys
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import TypeVar, cast

# Define the project root
ROOT_DIR = Path(__file__).parent.parent.resolve()

# Type variables for function signatures
T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., T])


def run_command(cmd: list[str], cwd: Path | None = None) -> int:
    """
    Run a shell command in the specified directory.

    Args:
        cmd: Command and arguments to run
        cwd: Working directory for the command

    Returns:
        int: Return code from the command
    """
    try:
        process = subprocess.run(
            cmd,
            cwd=cwd or ROOT_DIR,
            check=True,
        )
        return process.returncode
    except subprocess.CalledProcessError as e:
        print(f"Command {' '.join(cmd)} failed with exit code {e.returncode}")
        return e.returncode


def command(func: F) -> F:
    """
    Decorator for command functions.

    Args:
        func: Function to decorate

    Returns:
        Decorated function that handles exceptions
    """

    @wraps(func)
    def wrapper(*args, **kwargs) -> T:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"Error: {e}")
            return cast(T, 1)

    return cast(F, wrapper)


@command
def run_server(debug: bool = True) -> int:
    """
    Run the development server.

    Args:
        debug: Whether to run in debug mode

    Returns:
        int: Exit code
    """
    os.environ["DEBUG"] = "True" if debug else "False"
    return run_command(["python", "-m", "app.main"])


@command
def test(args: list[str] = None) -> int:
    """
    Run tests with pytest.

    Args:
        args: Additional pytest arguments

    Returns:
        int: Exit code
    """
    cmd = ["pytest"]
    if args:
        cmd.extend(args)
    return run_command(cmd)


@command
def format_code() -> int:
    """
    Format code using Ruff.

    Returns:
        int: Exit code
    """
    return run_command(["ruff", "format", str(ROOT_DIR)])


@command
def lint(fix: bool = True) -> int:
    """
    Run Ruff linters with auto-fix.

    Args:
        fix: Whether to automatically fix issues

    Returns:
        int: Exit code
    """
    cmd = ["ruff", "check"]
    if fix:
        cmd.append("--fix")
    cmd.append(str(ROOT_DIR))
    return run_command(cmd)


@command
def clean() -> int:
    """
    Clean up temporary project files.

    Returns:
        int: Exit code
    """
    patterns = [
        "**/__pycache__",
        "**/.pytest_cache",
        "**/.ruff_cache",
        "**/*.pyc",
        "**/*.pyo",
        "**/build",
        "**/dist",
        "**/*.egg-info",
    ]

    for pattern in patterns:
        for path in ROOT_DIR.glob(pattern):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                import shutil

                shutil.rmtree(path)

    return 0


def main() -> int:
    """
    Main entry point for the script.

    Returns:
        int: Exit code
    """
    if len(sys.argv) < 2:
        print("Available commands:")
        print("  run - Run the development server")
        print("  test - Run tests")
        print("  format - Format code")
        print("  lint - Run linters")
        print("  clean - Clean up temporary files")
        return 0

    command_name = sys.argv[1]
    args = sys.argv[2:]

    commands = {
        "run": run_server,
        "test": test,
        "format": format_code,
        "lint": lint,
        "clean": clean,
    }

    if command_name not in commands:
        print(f"Unknown command: {command_name}")
        return 1

    if command_name == "test":
        return commands[command_name](args)

    return commands[command_name]()


if __name__ == "__main__":
    sys.exit(main())
