from app.config import Settings
from app.services.storage import DatasetStorageService
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

_settings = Settings.from_ini()


def get_settings() -> Settings:
    return _settings


def get_storage_service() -> DatasetStorageService:
    return DatasetStorageService(storage_root=_settings.file_storage_path)


def get_model() -> BaseChatModel:
    if _settings.openai_api_key:
        return ChatOpenAI(
            model="gpt-4o-mini",
            api_key=_settings.openai_api_key,
        )
    if _settings.anthropic_api_key:
        return ChatAnthropic(
            model="claude-3-5-sonnet-20240620",
            api_key=_settings.anthropic_api_key,
        )
    raise ValueError("No LLM API key configured")
