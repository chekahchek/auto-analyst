import pytest
from app.services.exceptions import InvalidFileError
from app.services.storage import DatasetStorageService
from uuid import UUID


@pytest.fixture
def storage_service(tmp_path):
    from app.services.storage import DatasetStorageService
    return DatasetStorageService(storage_root=tmp_path)


class TestValidateExtension:
    def test_accepts_lowercase_csv(self):
        DatasetStorageService.validate_extension("data.csv")  # should not raise

    def test_accepts_uppercase_csv(self):
        DatasetStorageService.validate_extension("data.CSV")  # should not raise

    def test_rejects_txt(self):
        with pytest.raises(InvalidFileError):
            DatasetStorageService.validate_extension("data.txt")

    def test_rejects_xlsx(self):
        with pytest.raises(InvalidFileError):
            DatasetStorageService.validate_extension("data.xlsx")

    def test_rejects_missing_filename(self):
        with pytest.raises(InvalidFileError):
            DatasetStorageService.validate_extension(None)

class TestPathFor:
    def test_returns_expected_path(self, storage_service):
        dataset_id = UUID(int=0)
        path = storage_service.path_for(dataset_id)
        assert path == storage_service.storage_root / "datasets" / str(dataset_id) / "input.csv"


class TestDelete:
    async def test_removes_existing_file(self, storage_service):
        dataset_id = UUID(int=0)
        path = storage_service.path_for(dataset_id)
        path.parent.mkdir(parents=True)
        path.write_text("a,b\n1,2\n")

        await storage_service.delete(dataset_id)

        assert not path.exists()

    async def test_missing_file_is_silent(self, storage_service):
        dataset_id = UUID(int=0)
        await storage_service.delete(dataset_id)  # should not raise
