from pathlib import Path

from app.services.exceptions import InvalidFileError


class DatasetStorageService:
    def __init__(self, storage_root: Path):
        self.storage_root = storage_root

    @staticmethod
    def validate_extension(filename: str | None) -> None:
        if not filename:
            raise InvalidFileError("Filename is required")
        if not filename.lower().endswith(".csv"):
            raise InvalidFileError(f"Only .csv files are supported: {filename}")
