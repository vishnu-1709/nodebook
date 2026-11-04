"""Uvicorn factory target for development: ``uvicorn backend.devserver:app --factory``."""

from backend.app import create_app


def app():  # noqa: ANN201
    return create_app()
