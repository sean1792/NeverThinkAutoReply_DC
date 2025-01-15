import json
import os
import time

import requests
from httpx import NetworkError

from src.configs import configs, WRITABLE_PATH
from src.utils.logger import get_logger

logger = get_logger(__name__)


def get_mygo_data(key: str):
    logger.info("開始獲取 Mygo 數據")
    logger.debug(f"使用關鍵字: {key}")

    try:
        api_url = configs["API"].get("mygo").format(key=key)
        logger.debug(f"請求 API: {api_url}")

        response = requests.get(api_url)
        response.raise_for_status()
        logger.debug("API 請求成功")

        data = response.content.decode("utf-8")
        result = json.loads(data)["urls"][0]
        logger.info("成功解析 Mygo 數據")
        logger.debug(f"獲取的數據: {result}")

        return result
    except requests.exceptions.RequestException as e:
        logger.error(f"API 請求失敗: {str(e)}", exc_info=True)
        raise RuntimeError(f"API 請求失敗: {str(e)}")
    except json.JSONDecodeError as e:
        logger.error(f"JSON 解析失敗: {str(e)}", exc_info=True)
        raise RuntimeError(f"JSON 解析失敗: {str(e)}")
    except KeyError as e:
        logger.error(f"數據結構錯誤: {str(e)}", exc_info=True)
        raise RuntimeError(f"數據結構錯誤: {str(e)}")
    except Exception as e:
        logger.error(f"獲取 Mygo 數據時發生未預期的錯誤: {str(e)}", exc_info=True)
        raise RuntimeError(f"獲取 Mygo 數據時發生未預期的錯誤: {str(e)}")


def download_mygo(data: dict):
    logger.info("開始下載 Mygo 圖片")
    logger.debug(f"圖片數據: {data}")

    target_path = os.path.join(WRITABLE_PATH, "downloaded")
    try:
        if not os.path.exists(target_path):
            logger.debug(f"創建目標目錄: {target_path}")
            os.makedirs(target_path)

        file_path = os.path.join(target_path, f"{data['alt']}.jpg")
        logger.debug(f"目標文件路徑: {file_path}")

        logger.debug(f"開始下載圖片: {data['url']}")
        response = requests.get(data["url"], stream=True)
        response.raise_for_status()

        total_size = 0
        with open(file_path, 'wb') as file:
            for chunk in response.iter_content(1024):
                file.write(chunk)
                total_size += len(chunk)

        logger.info(f"圖片下載成功: {file_path}")
        logger.debug(f"文件大小: {total_size / 1024:.2f}KB")
        return True

    except requests.exceptions.RequestException as e:
        logger.error(f"下載圖片請求失敗: {str(e)}", exc_info=True)
        return False
    except IOError as e:
        logger.error(f"文件寫入失敗: {str(e)}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"下載圖片時發生未預期的錯誤: {str(e)}", exc_info=True)
        return False


if __name__ == '__main__':
    try:
        logger.info("開始測試 Mygo 功能")
        data = get_mygo_data("")
        logger.info("成功獲取 Mygo 數據")

        if download_mygo(data):
            logger.info("測試完成: 圖片下載成功")
        else:
            logger.error("測試完成: 圖片下載失敗")

    except Exception as e:
        logger.error(f"測試過程中發生錯誤: {str(e)}", exc_info=True)