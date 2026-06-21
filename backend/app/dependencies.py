from app.config import Settings
from app.services.storage import DatasetStorageService
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

_settings = Settings.from_ini()


def get_settings() -> Settings:
    return _settings


def get_storage_service() -> DatasetStorageService:
    return DatasetStorageService(storage_root=_settings.file_storage_path)


def get_model() -> BaseChatModel:
    if _settings.model and _settings.api_key and _settings.api_base_url:
        return ChatOpenAI(
            model=_settings.model,
            api_key=_settings.api_key,
            base_url=_settings.api_base_url,
        )
    else:
        raise ValueError(
            "Model configuration is incomplete. Please check your settings."
        )
