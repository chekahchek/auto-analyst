class StorageError(Exception):
    """Raised when a filesystem-level operation fails."""


class InvalidFileError(StorageError):
    """Raised when the uploaded file fails basic validation (e.g., wrong extension)."""


class MalformedCSVError(StorageError):
    """Raised when the file cannot be parsed as CSV."""
