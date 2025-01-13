import os

import logging
from logging.handlers import RotatingFileHandler
from src.configs import WRITABLE_PATH

def get_logger(module_name, log_level=logging.INFO, max_bytes=5*1024*1024, backup_count=5):
    """
    獲取共享 logger 實例。

    :param module_name: 模組名稱（通常為 __name__）
    :param log_level: log 等級
    :param max_bytes: 單個 log 檔案的最大大小（預設 5 MB）
    :param backup_count: 保留的歷史 log 檔案數量
    :return: logger 實例
    """
    log_file_path = os.path.join(WRITABLE_PATH, f"app.log")

    logger = logging.getLogger(module_name)

    if not logger.hasHandlers():
        logger.setLevel(log_level)

        handler = RotatingFileHandler(log_file_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
