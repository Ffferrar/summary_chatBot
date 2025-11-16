"""
Модуль для настройки логирования.
"""

import logging

LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"

def setup_logging(log_file="bot.log"):
    """
    Настраивает логирование для приложения.
    :param log_file: Имя файла для записи логов.
    """
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file, encoding="utf-8")
        ]
    )
    logger = logging.getLogger(__name__)
    logger.info("Логирование настроено.")
