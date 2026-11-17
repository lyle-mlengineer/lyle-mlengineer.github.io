"""Upload and parse failures with HTTP-friendly status codes."""


class DocumentError(ValueError):
    """A file that cannot be accepted into a run."""

    status_code = 422

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        if status_code is not None:
            self.status_code = status_code


class DocumentTooLarge(DocumentError):
    status_code = 413


class UnsupportedDocument(DocumentError):
    pass


class MalwareDetected(DocumentError):
    pass


class PageLimitExceeded(DocumentError):
    def __init__(self, pages: int, limit: int, *, unit: str = "pages") -> None:
        super().__init__(f"{pages} {unit} exceeds the {limit}-{unit} limit")
        self.pages = pages
        self.limit = limit


class MalformedDocument(DocumentError):
    def __init__(self, filename: str, detail: str) -> None:
        detail = " ".join(detail.split())[:200]
        super().__init__(f"{filename}: malformed or unreadable document ({detail})")
