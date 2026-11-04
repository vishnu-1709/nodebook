from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.core.settings import Settings, SettingsStore
from backend.llm.fake import FakeProvider


@pytest.fixture()
def data_dir(tmp_path: Path) -> Path:
    d = tmp_path / "data"
    d.mkdir()
    return d


@pytest.fixture()
def settings_store(tmp_path: Path, data_dir: Path) -> SettingsStore:
    store = SettingsStore(tmp_path / "config")
    store.save(Settings(data_dir=str(data_dir), map_model="fake-map:latest", study_model="fake-study:latest"))
    return store


@pytest.fixture()
def fake() -> FakeProvider:
    return FakeProvider()


@pytest.fixture()
def app(settings_store: SettingsStore, fake: FakeProvider, tmp_path: Path):  # noqa: ANN201
    return create_app(settings_store=settings_store, provider=fake, static_dir=tmp_path / "nostatic")


@pytest.fixture()
def client(app) -> Iterator[TestClient]:  # noqa: ANN001
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def ctx(app):  # noqa: ANN001, ANN201
    return app.state.ctx
