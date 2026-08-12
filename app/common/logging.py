import logging
import sys

logger = logging.getLogger("app")
logger.setLevel(logging.INFO)
_handler = logging.StreamHandler(sys.stdout)
_formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
_handler.setFormatter(_formatter)
logger.handlers.clear()
logger.addHandler(_handler)
