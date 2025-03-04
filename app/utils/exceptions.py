"""Exception utilities for the application."""

from typing import NoReturn

from fastapi import HTTPException, status


def raise_server_error(message: str, error: Exception) -> NoReturn:
    """
    Raise a 500 Internal Server Error exception.

    Args:
        message: Error message
        error: Exception that caused the error

    Raises:
        HTTPException: 500 Internal Server Error exception
    """
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"{message}: {str(error)}",
    ) from error
