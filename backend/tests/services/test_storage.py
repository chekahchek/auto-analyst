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


def test_validation_extensions():
    assert DatasetStorageService.validate_extension("data.csv") is None
    assert DatasetStorageService.validate_extension("data.CSV") is None

    with pytest.raises(InvalidFileError):
        DatasetStorageService.validate_extension("data.txt")


def test_returns_expected_path(storage_service):
    dataset_id = UUID(int=0)
    path = storage_service.obtain_file_path(dataset_id)
    assert (
        path
        == storage_service.storage_root / "datasets" / str(dataset_id) / "input.csv"
    )


def test_path_for_returns_expected_path(storage_service):
    dataset_id = UUID(int=0)
    path = storage_service.obtain_file_path(dataset_id)
    assert (
        path
        == storage_service.storage_root / "datasets" / str(dataset_id) / "input.csv"
    )


async def test_writes_valid_csv(storage_service):
    dataset_id = UUID(int=0)
    content = b"a,b\n1,2\n3,4\n"
    file = UploadFile(filename="data.csv", file=BytesIO(content))

    path = await storage_service.save(file, dataset_id)

    assert path == storage_service.obtain_file_path(dataset_id)
    assert path.read_text() == content.decode()


async def test_rejects_empty_csv(storage_service):
    dataset_id = UUID(int=0)
    file = UploadFile(filename="data.csv", file=BytesIO(b""))

    with pytest.raises(MalformedCSVError):
        await storage_service.save(file, dataset_id)

    assert not storage_service.obtain_file_path(dataset_id).exists()
    assert not storage_service.obtain_file_path(dataset_id).parent.exists()


async def test_rejects_non_csv_filename(storage_service):
    dataset_id = UUID(int=0)
    file = UploadFile(filename="data.txt", file=BytesIO(b"a,b\n1,2\n"))

    with pytest.raises(InvalidFileError):
        await storage_service.save(file, dataset_id)

    assert not storage_service.obtain_file_path(dataset_id).exists()
    assert not storage_service.obtain_file_path(dataset_id).parent.exists()
