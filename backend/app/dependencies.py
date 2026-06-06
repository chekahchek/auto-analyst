from app.config import Settings

_settings = Settings.from_ini()


def get_settings() -> Settings:
    return _settings
