from io import BytesIO
import win32clipboard
from PIL import Image
from src.utils.logger import get_logger

logger = get_logger(__name__)


def send_to_clipboard(clip_type, data):
    logger.info("開始寫入剪貼板")
    try:
        logger.debug("打開剪貼板")
        win32clipboard.OpenClipboard()

        logger.debug("清空剪貼板")
        win32clipboard.EmptyClipboard()

        logger.debug(f"設置剪貼板數據 (類型: {clip_type})")
        win32clipboard.SetClipboardData(clip_type, data)

        logger.debug("關閉剪貼板")
        win32clipboard.CloseClipboard()

        logger.info("成功寫入剪貼板")

    except win32clipboard.error as e:
        logger.error(f"剪貼板操作失敗: {str(e)}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"寫入剪貼板時發生未預期的錯誤: {str(e)}", exc_info=True)
        raise


def copy_image(filepath):
    logger.info(f"開始複製圖片到剪貼板: {filepath}")
    try:
        logger.debug("開始讀取圖片文件")
        image = Image.open(filepath)
        logger.debug(f"成功讀取圖片: {image.format}, {image.size}, {image.mode}")

        logger.debug("轉換圖片格式")
        output = BytesIO()
        image.convert("RGB").save(output, "BMP")

        logger.debug("處理圖片數據")
        data = output.getvalue()[14:]
        output.close()

        logger.debug("寫入剪貼板")
        send_to_clipboard(win32clipboard.CF_DIB, data)

        logger.info("成功複製圖片到剪貼板")

    except FileNotFoundError:
        logger.error(f"找不到圖片文件: {filepath}", exc_info=True)
        raise
    except IOError as e:
        logger.error(f"讀取圖片文件失敗: {str(e)}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"複製圖片時發生未預期的錯誤: {str(e)}", exc_info=True)
        raise


if __name__ == '__main__':
    try:
        logger.info("開始測試圖片複製功能")
        test_image = '../../assets/icons/speaking.png'
        copy_image(test_image)
        logger.info("測試完成")

    except Exception as e:
        logger.error(f"測試過程中發生錯誤: {str(e)}", exc_info=True)