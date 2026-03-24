"""Logging setup helpers for consistent structured console output."""

from __future__ import annotations

import logging


def setup_logging(log_level: str) -> None:
    """Configure root logging handlers and formatters exactly once."""
    if logging.getLogger().handlers:
        logging.getLogger().setLevel(log_level)
        return

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
