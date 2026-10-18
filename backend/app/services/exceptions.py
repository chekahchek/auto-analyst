from uuid import UUID


class StorageError(Exception):
    """Raised when a filesystem-level operation fails."""


class InvalidFileError(StorageError):
    """Raised when the uploaded file fails basic validation (e.g., wrong extension)."""


class MalformedCSVError(StorageError):
    """Raised when the file cannot be parsed as CSV."""


class SessionNotFoundError(Exception):
    """Raised when a session does not exist or is not owned by the user."""


class AnalysisFailedError(Exception):
    """Raised when a chat turn fails after the session ownership check."""

    def __init__(self, reference_id: UUID):
        super().__init__(f"Analysis failed reference_id={reference_id}")
        self.reference_id = reference_id
