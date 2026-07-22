import logging
import sys

from app.core import settings


def configure_logger(
    name: str = "fastapi",
    level: int = settings.LOG_LEVEL,
) -> logging.Logger:
    logger: logging.Logger = logging.getLogger(name)

    # 중복 핸들러 방지
    if logger.handlers:
        return logger

    logger.setLevel(level)

    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s %(name)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 콘솔 출력
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.propagate = False  # root logger로 중복 전달 방지

    return logger
