import pytest
from app.services.exceptions import InvalidFileError
from app.services.storage import DatasetStorageService


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

    def test_rejects_empty_filename(self):
        with pytest.raises(InvalidFileError):
            DatasetStorageService.validate_extension("")
