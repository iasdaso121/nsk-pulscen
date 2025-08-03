class ScraperError(Exception):
    """Base class for scraper-related exceptions."""

class FetchError(ScraperError):
    """Raised when fetching a page fails permanently."""

class ParseError(ScraperError):
    """Raised when parsing a page fails."""

class StorageError(ScraperError):
    """Raised when storing data fails."""
