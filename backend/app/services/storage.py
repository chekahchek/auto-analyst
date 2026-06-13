import asyncio
import shutil
from pathlib import Path
from uuid import UUID

import pandas as pd
from fastapi import UploadFile

from app.services.exceptions import InvalidFileError, MalformedCSVError, StorageError


class DatasetStorageService:
    def __init__(self, storage_root: Path):
        self.storage_root = storage_root

    def obtain_file_path(self, dataset_id: UUID) -> Path:
        return self.storage_root / "datasets" / str(dataset_id) / "input.csv"

    async def save(self, file: UploadFile, dataset_id: UUID) -> Path:
        self.validate_extension(file.filename)
        target = self.obtain_file_path(dataset_id)
        await file.seek(0)

        try:
            return await asyncio.to_thread(self._write_and_validate, target, file)
        except (InvalidFileError, MalformedCSVError):
            await asyncio.to_thread(self._cleanup_sync, target)
            raise
        except Exception as exc:
            await asyncio.to_thread(self._cleanup_sync, target)
            raise StorageError(f"Failed to save dataset file: {exc}") from exc

    async def delete(self, dataset_id: UUID) -> None:
        path = self.obtain_file_path(dataset_id)
        await asyncio.to_thread(self._cleanup_sync, path)

    @staticmethod
    def _write_and_validate(target: Path, file: UploadFile) -> Path:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        try:
            pd.read_csv(target, nrows=5)
        except pd.errors.EmptyDataError:
            raise MalformedCSVError("CSV file is empty") from None
        except pd.errors.ParserError as exc:
            raise MalformedCSVError(f"File is not a valid CSV: {exc}") from exc
        return target

    @staticmethod
    def _cleanup_sync(path: Path) -> None:
        if path.exists():
            path.unlink()
        try:
            path.parent.rmdir()
        except OSError:
            pass

    @staticmethod
    def validate_extension(filename: str | None) -> None:
        if not filename:
            raise InvalidFileError("Filename is required")
        if not filename.lower().endswith(".csv"):
            raise InvalidFileError(f"Only .csv files are supported: {filename}")
