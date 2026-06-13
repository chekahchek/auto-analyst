from pathlib import Path
from unittest.mock import MagicMock

import app.dependencies as dependencies
from app.dependencies import get_storage_service


def test_get_storage_service_uses_configured_root(monkeypatch):
    mock_settings = MagicMock()
    mock_settings.file_storage_path = Path("/tmp/test-data")
    monkeypatch.setattr(dependencies, "_settings", mock_settings)

    service = get_storage_service()

    assert service.storage_root == Path("/tmp/test-data")
