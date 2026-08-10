import logging
import sys
from pathlib import Path
from typing import Optional

LogLevel = int

_CONSOLE_FORMAT = "%(levelname)s %(name)s: %(message)s"
_FILE_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_DATE_FORMAT = "%H:%M:%S"

_EMOJI_MAP = {
    logging.ERROR: "  ERROR",
    logging.WARNING: "  WARNING",
    logging.INFO: "  INFO",
    logging.DEBUG: "  DEBUG",
}


class _EmojiFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        prefix = _EMOJI_MAP.get(record.levelno, "")
        record.levelname = prefix
        return super().format(record)


def setup_logging(
    level: LogLevel = logging.INFO,
    log_file: Optional[Path] = None,
    console: bool = True,
) -> None:
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    handler: logging.Handler | None = None
    if console:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        handler.setFormatter(
            _EmojiFormatter(_CONSOLE_FORMAT, datefmt=_DATE_FORMAT)
        )
        root.addHandler(handler)

    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(log_file, encoding="utf-8")
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(
            logging.Formatter(_FILE_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")
        )
        root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
