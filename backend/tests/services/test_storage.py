import pytest
from app.services.exceptions import InvalidFileError, MalformedCSVError
from app.services.storage import DatasetStorageService
from uuid import UUID
from io import BytesIO
from fastapi import UploadFile


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
        assert (
            path
            == storage_service.storage_root / "datasets" / str(dataset_id) / "input.csv"
        )


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


class TestSave:
    async def test_writes_valid_csv(self, storage_service):
        dataset_id = UUID(int=0)
        content = b"a,b\n1,2\n3,4\n"
        file = UploadFile(filename="data.csv", file=BytesIO(content))

        path = await storage_service.save(file, dataset_id)

        assert path == storage_service.path_for(dataset_id)
        assert path.read_text() == content.decode()

    async def test_creates_parent_directories(self, storage_service):
        dataset_id = UUID(int=0)
        file = UploadFile(filename="data.csv", file=BytesIO(b"a,b\n1,2\n"))

        await storage_service.save(file, dataset_id)

        assert storage_service.path_for(dataset_id).exists()

    async def test_rejects_malformed_csv(self, storage_service):
        dataset_id = UUID(int=0)
        # Unclosed quote causes pandas ParserError
        file = UploadFile(filename="data.csv", file=BytesIO(b'a,b\n1,"2\n'))

        with pytest.raises(MalformedCSVError):
            await storage_service.save(file, dataset_id)

        assert not storage_service.path_for(dataset_id).exists()

    async def test_rejects_non_csv_filename(self, storage_service):
        dataset_id = UUID(int=0)
        file = UploadFile(filename="data.txt", file=BytesIO(b"a,b\n1,2\n"))

        with pytest.raises(InvalidFileError):
            await storage_service.save(file, dataset_id)
