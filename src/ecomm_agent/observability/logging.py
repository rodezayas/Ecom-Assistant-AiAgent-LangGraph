"""Logging configuration.

Configures the Python standard-library logging used across the application.
Kept intentionally simple; structured per-conversation observability is a
planned enhancement.
"""

import logging


def configure_logging() -> None:
    """Configure root logging at ``INFO`` level with a basic formatter."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
