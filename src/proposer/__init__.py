"""FastAPI-based proposer service for generating JSON patches."""

from .server import create_app

__all__ = ["create_app"]
