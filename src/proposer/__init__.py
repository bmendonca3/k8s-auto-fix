"""Proposer package helpers."""

from typing import Any


def create_app(*args: Any, **kwargs: Any) -> Any:
    """Create the FastAPI proposer app without importing server deps eagerly."""
    from .server import create_app as _create_app

    return _create_app(*args, **kwargs)

__all__ = ["create_app"]
