from pathlib import Path
from unittest.mock import MagicMock

import pytest
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

import app.dependencies as dependencies
from app.dependencies import get_storage_service


def test_get_storage_service_uses_configured_root(monkeypatch):
    mock_settings = MagicMock()
    mock_settings.file_storage_path = Path("/tmp/test-data")
    monkeypatch.setattr(dependencies, "_settings", mock_settings)

    service = get_storage_service()

    assert service.storage_root == Path("/tmp/test-data")


def test_get_model_returns_openai_when_openai_key_configured(monkeypatch):
    mock_settings = MagicMock()
    mock_settings.openai_api_key = "test-openai-key"
    mock_settings.anthropic_api_key = None
    monkeypatch.setattr(dependencies, "_settings", mock_settings)

    model = dependencies.get_model()

    assert isinstance(model, ChatOpenAI)


def test_get_model_returns_anthropic_when_only_anthropic_key_configured(monkeypatch):
    mock_settings = MagicMock()
    mock_settings.openai_api_key = None
    mock_settings.anthropic_api_key = "test-anthropic-key"
    monkeypatch.setattr(dependencies, "_settings", mock_settings)

    model = dependencies.get_model()

    assert isinstance(model, ChatAnthropic)


def test_get_model_raises_when_no_key_configured(monkeypatch):
    mock_settings = MagicMock()
    mock_settings.openai_api_key = None
    mock_settings.anthropic_api_key = None
    monkeypatch.setattr(dependencies, "_settings", mock_settings)

    with pytest.raises(ValueError):
        dependencies.get_model()
