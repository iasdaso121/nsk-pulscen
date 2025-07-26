import os
import re

"""Project configuration loaded from environment variables."""

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")


def validate() -> None:
    """Validate configuration values and raise ``ValueError`` on problems."""
    if not re.match(r"^mongodb(\+srv)?://", MONGODB_URI):
        raise ValueError(f"Invalid MongoDB URI: {MONGODB_URI}")

