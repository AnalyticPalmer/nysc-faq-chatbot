"""Configure logging for the NYSC FAQ Chatbot."""

import logging
from pathlib import Path


LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "chatbot.log"
LOGGER_NAME = "NYSCFAQChatbot"


def get_logger() -> logging.Logger:
    """Create or retrieve the configured chatbot logger.

    Returns:
        A logger that writes INFO-level messages and above to both a file
        and the terminal.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    chatbot_logger = logging.getLogger(LOGGER_NAME)
    chatbot_logger.setLevel(logging.INFO)

    # Stop messages from also being handled by the root logger.
    chatbot_logger.propagate = False

    # Reuse existing handlers when this module is imported more than once.
    if not chatbot_logger.handlers:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        file_handler = logging.FileHandler(
            LOG_FILE,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)

        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)

        chatbot_logger.addHandler(file_handler)
        chatbot_logger.addHandler(stream_handler)

    return chatbot_logger


logger = get_logger()


def main() -> None:
    """Write sample messages at three logging levels."""
    logger.info("NYSC FAQ Chatbot logger is working.")
    logger.warning("This is a sample warning message.")
    logger.error("This is a sample error message.")


if __name__ == "__main__":
    main()
