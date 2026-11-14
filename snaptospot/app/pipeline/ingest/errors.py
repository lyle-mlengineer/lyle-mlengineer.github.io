class CrawlError(RuntimeError):
    """Raised when a site cannot be crawled for a reason the user should see."""


class UnsafeURLError(CrawlError):
    """Raised when a URL points at a private, local or unsupported destination."""
