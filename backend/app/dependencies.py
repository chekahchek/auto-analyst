from app.config import Settings
from app.services.storage import DatasetStorageService

_settings = Settings.from_ini()


def get_settings() -> Settings:
    return _settings


def get_storage_service() -> DatasetStorageService:
    return DatasetStorageService(storage_root=_settings.file_storage_path)
