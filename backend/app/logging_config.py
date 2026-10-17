import logging.config
from typing import Any


def build_logging_config(log_level: str = "INFO") -> dict[str, Any]:
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            # Per-request / per-statement INFO noise. Pinned to WARNING so that
            # LOG_LEVEL=INFO shows app events only. Raise to INFO to debug them.
            "httpx": {"level": "WARNING"},
            "httpcore": {"level": "WARNING"},
            "sqlalchemy.engine": {"level": "WARNING"},
        },
        "root": {
            "level": log_level.upper(),
            "handlers": ["console"],
        },
    }


def configure_logging(log_level: str = "INFO") -> None:
    logging.config.dictConfig(build_logging_config(log_level))
