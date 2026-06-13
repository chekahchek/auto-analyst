import asyncio
from pathlib import Path
from uuid import UUID

from app.services.exceptions import InvalidFileError


class DatasetStorageService:
    def __init__(self, storage_root: Path):
        self.storage_root = storage_root

    def path_for(self, dataset_id: UUID) -> Path:
        return self.storage_root / "datasets" / str(dataset_id) / "input.csv"

    async def delete(self, dataset_id: UUID) -> None:
        path = self.path_for(dataset_id)

        def _remove() -> None:
            if path.exists():
                path.unlink()

        await asyncio.to_thread(_remove)

    @staticmethod
    def validate_extension(filename: str | None) -> None:
        if not filename:
            raise InvalidFileError("Filename is required")
        if not filename.lower().endswith(".csv"):
            raise InvalidFileError(f"Only .csv files are supported: {filename}")
