import logging
import os


def _configure_logging() -> None:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, None)
    is_invalid_level = level is None or not isinstance(level, int)
    if is_invalid_level:
        level = logging.INFO
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        logging.basicConfig(
            level=level,
            format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        )
    root_logger.setLevel(level)
    if is_invalid_level:
        logging.getLogger(__name__).warning(
            "Invalid LOG_LEVEL=%s provided; defaulting to INFO", level_name
        )


_configure_logging()
