import os
import sys
import time
import logging
from enum import Enum, auto
import threading
from functools import partial
import asyncio

import pyperclip
import pyautogui
from pynput import keyboard
from pynput.mouse import Listener, Button
from PIL import ImageGrab, Image, ImageEnhance
import easyocr
import cv2

from PySide6.QtCore import Qt, QSize, QPoint, QFile, QTextStream, Signal, QObject, QTimer
from PySide6.QtGui import QCursor, QIcon
from PySide6.QtWidgets import QApplication, QHBoxLayout, QPushButton, QVBoxLayout, QWidget, QSystemTrayIcon, QMenu
from windows_toasts import WindowsToaster, Toast, ToastDisplayImage, ToastDuration

from src.api.llm import get_llm
from src.utils.copy_ import copy_image
from src.configs import APP_ROOT_PATH, WRITABLE_PATH, configs
from src.utils.logger import get_logger

# ###########################################
# Notify
# ###########################################

def show_notify(text: str = "你點一下輸入框! 我來回...", icon: str = None):
    toast = Toast()
    toast.duration = ToastDuration.Short
    logger.info(f"顯示通知: {text}")
    toast.text_fields = [text]
    if icon:
        logger.debug(f"使用圖標: {icon}")
        toast.AddImage(ToastDisplayImage.fromPath(icon))
    toaster.show_toast(toast)

# ###########################################
# Initialize Instances
# ###########################################

lang_map = {
    'zh-cn': 'ch_sim',
    'zh-tw': 'ch_tra',
}

lang_cfg = configs["General"].get("ocr_lang", "zh-tw")
lang = lang_map[lang_cfg]

logger = get_logger(__name__, logging.DEBUG)

HOTKEY = configs["General"].get("hotkey", "<ctrl>+<shift>+x")
BASE_MODEL = configs["General"].get("model_base", "openai")
ERROR_ICON = os.path.join(APP_ROOT_PATH, "assets/icons/error.png")
SUCCESS_ICON = os.path.join(APP_ROOT_PATH, "assets/icons/success.png")
TEMP_IMG_PATH = os.path.join(WRITABLE_PATH, "assets/temp/temp.jpg")

toaster = WindowsToaster("NeverThinkAutoReply")

try:
    llm = get_llm(BASE_MODEL)
except ValueError as e:
    show_notify(text=f"請至 'config.ini' 文件內的[Keys] '{BASE_MODEL}' 欄位填入API Key",
                icon=ERROR_ICON)
    sys.exit(1)
except Exception as e:
    logger.error(f"LLM 初始化失敗: {str(e)}")
    sys.exit(1)

# ###########################################
# Enums & Maps
# ###########################################

class Method(Enum):
    NORMAL = auto()
    REFUTE = auto()
    TOXIC = auto()
    MYGO = auto()
    MUJICA = auto()


METHODS = {
    Method.NORMAL: {
        "icon": os.path.join(APP_ROOT_PATH, "assets/icons/comment.png"),
        "text": "正常",
        "type": Method.NORMAL,
    },
    Method.REFUTE: {
        "icon": os.path.join(APP_ROOT_PATH, "assets/icons/thinking.png"),
        "text": "反駁",
        "type": Method.REFUTE,
    },
    Method.TOXIC: {
        "icon": os.path.join(APP_ROOT_PATH, "assets/icons/speaking.png"),
        "text": "嘲諷",
        "type": Method.TOXIC,
    },
    Method.MYGO: {
        "icon": os.path.join(APP_ROOT_PATH, "assets/icons/guitar.png"),
        "text": "MyGO",
        "type": Method.MYGO,
    },
    Method.MUJICA: {
        "icon": os.path.join(APP_ROOT_PATH, "assets/icons/theater.png"),
        "text": "Mujica",
        "type": Method.MUJICA,
    }
}

# ###########################################
# Signals
# ###########################################

class HotKeySignals(QObject):
    triggered = Signal()

class StatusSignals:
    task_running = threading.Event()
    window_status = False

hotkey_signal_slots = HotKeySignals()
status_signal_slots = StatusSignals()

# ###########################################
# Utils
# ###########################################

async def do_copy():
    await asyncio.sleep(0.5)
    pyautogui.hotkey('ctrl', 'c')
    await asyncio.sleep(0.5)

    hotkey_signal_slots.triggered.emit()

def do_paste():
    time.sleep(0.5)
    pyautogui.hotkey('ctrl', 'v')

# ###########################################
# Listeners
# ###########################################

def mouse_on_click_action(x, y, button, pressed):
    if pressed:
        if button == Button.left:
            threading.Thread(target=do_paste, daemon=True).start()
            return False

def on_hotkey_triggered():
    logger.info("快捷鍵觸發")
    asyncio.run(do_copy())

hotkey_listener = keyboard.GlobalHotKeys({HOTKEY: on_hotkey_triggered})
hotkey_listener.start()

# ###########################################
# Processor
# ###########################################

def ocr(img: Image.Image) -> str:
    text_content = ""

    img.save(TEMP_IMG_PATH)
    target_image = cv2.imread(TEMP_IMG_PATH)
    target_image = cv2.cvtColor(target_image, cv2.COLOR_BGR2GRAY)
    cv2.imwrite(TEMP_IMG_PATH, target_image)
    ocr_reader = easyocr.Reader([lang])  # OCR支援語言 : 繁體、簡體
    result = ocr_reader.readtext(TEMP_IMG_PATH)

    for detection in result:
        text_content += detection[1]
    logger.info(f"OCR檢測文字內容: {text_content if len(text_content) <= 100 else f'{text_content[:100]}...'}")

    return text_content

def process(method: Method):  # second thread
    try:
        target_text_content = pyperclip.paste()
        target_img_content = ImageGrab.grabclipboard()

        logger.info(f"target_text_content: {target_text_content if len(target_text_content) <= 100 else f'{target_text_content[:100]}...'}")
        logger.info(f"target_img_content: {target_img_content}")

        if not target_text_content and not target_img_content:
            logger.warning("剪貼板是空的")
            show_notify(text="請先反白要針對回覆的內容，或是複製圖片到剪貼版！",
                        icon=ERROR_ICON)
            return

        if isinstance(target_img_content, Image.Image):
            try:
                target_text_content = ocr(target_img_content)
            except Exception as e:
                show_notify(text=f"OCR發生錯誤: {str(e)}",
                            icon=ERROR_ICON)
                return

        logger.info(f"向 {BASE_MODEL} 發送請求")
        
        is_res_image = (method == Method.MYGO or method == Method.MUJICA)
        max_tokens = 32 if is_res_image else 500 # 如果只需要回復圖片檔案名稱, 不應該生成那麼多 tokens
        
        try:
            res = llm.get_response(prompt=target_text_content, method=method.value, max_tokens=max_tokens)
            logger.info(f"{BASE_MODEL} 回應: {res if len(res) <= 100 else f'{res[:100]}...'}")
        except Exception as e:
            show_notify(text=f"{BASE_MODEL} API 處理中發生錯誤: {str(e)}",
                        icon=ERROR_ICON)
            return

        if is_res_image:
            mygo_or_mujica = "mygo" if method == Method.MYGO else "mujica"
            try:
                logger.info("處理 MyGo / Ave Mujica 類型回應")

                file_path = os.path.join(WRITABLE_PATH, "assets", mygo_or_mujica, res)

                if not os.path.exists(file_path):
                    raise FileNotFoundError(f"找不到圖片名: {res}, 路徑: {file_path}")

                logger.info(f"複製圖片到剪貼板: {file_path}")
                copy_image(file_path)
            except Exception as e:
                show_notify(text=str(e),
                            icon=ERROR_ICON)
                return
        else:
            logger.info("複製回覆到剪貼板")
            pyperclip.copy(res)

        show_notify(text="請點擊要貼上的位置 (輸入框)",
                    icon=SUCCESS_ICON)

        mouse_listener = Listener(on_click=lambda x, y, button, pressed:
                                  mouse_on_click_action(x, y, button, pressed))
        mouse_listener.start()
    finally:
        if os.path.exists(TEMP_IMG_PATH):
            os.remove(TEMP_IMG_PATH)

        status_signal_slots.task_running.clear()
        logger.info("'status_signal_slots.task_running' cleared")

# ###########################################
# Window
# ###########################################

class NeverThinkAutoReply(QWidget):
    def __init__(self):
        super().__init__()
        logger.info("初始化控制面板")

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        # Timers
        self.hide_timer = QTimer(self)
        self.hide_timer.timeout.connect(self.check_focus)
        self.hide_timer.start(100)

        # init
        self.init_hotkey_listener()

        self.init_ui()
        self.init_tray()

    def init_hotkey_listener(self):
        logger.info("初始化快捷鍵監聽")
        hotkey_signal_slots.triggered.connect(self.on_hotkey)

    def init_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(os.path.join(APP_ROOT_PATH, "assets/icons/huh.png")))

        tray_menu = QMenu()
        show_action = tray_menu.addAction("顯示")
        show_action.triggered.connect(self.show_below_cursor)
        quit_action = tray_menu.addAction("退出")
        quit_action.triggered.connect(self.close)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

        logger.debug("完成Windows Hidden Icons選單初始化")
        self.tray_icon.setToolTip(f"快捷鍵: {HOTKEY}")

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.menu_widget = QWidget()
        menu_layout = QHBoxLayout(self.menu_widget)
        menu_layout.setContentsMargins(0, 0, 0, 0)
        menu_layout.setSpacing(5)

        for btn_info in METHODS.values():
            button = QPushButton(btn_info["text"])
            button.setIcon(QIcon(btn_info["icon"]))
            button.setIconSize(QSize(24, 24))
            button.clicked.connect(
                partial(self.start_process, btn_info["type"]))
            button.setFixedSize(QSize(120, 40))
            menu_layout.addWidget(button)

        main_layout.addWidget(self.menu_widget)
        self.setLayout(main_layout)
        self.resize(500, 50)
        self.load_style_sheet()

    def start_process(self, method_type: Method):
        logger.info(f"開始處理: {method_type}")
        if not status_signal_slots.task_running.is_set():
            status_signal_slots.task_running.set()
            logger.info("'status_signal_slots.task_running' set")
            threading.Thread(target=lambda: process(method_type), daemon=True).start()
            self.hide()
        else:
            logger.info("任務正在執行中，忽略此次操作")
            show_notify(text="正在處理另一個任務", icon=ERROR_ICON)

    def on_hotkey(self):
        if (not status_signal_slots.window_status and
            not status_signal_slots.task_running.is_set()):
            logger.info("快捷鍵觸發: 顯示視窗")
            status_signal_slots.window_status = True
            logger.info(f"'status_signal_slots.window_status' has changed to {status_signal_slots.window_status}")
            self.show_below_cursor()
        else:
            logger.info("視窗已存在，忽略此次操作")
            show_notify(text="正在處理另一個任務", icon=ERROR_ICON)

    def load_style_sheet(self):
        logger.debug("加載StyleSheets")
        style_path = os.path.join(APP_ROOT_PATH, "assets/stylesheets/style.qss")
        file = QFile(style_path)
        if file.open(QFile.ReadOnly | QFile.Text):
            stream = QTextStream(file)
            style = stream.readAll()
            self.setStyleSheet(style)
        file.close()

    def show_below_cursor(self):
        cursor_pos = QCursor.pos()
        logger.info(f"顯示視窗: {cursor_pos.x()}, {cursor_pos.y()}")
        self.move(cursor_pos + QPoint(0, 20))
        self.show()
        self.activateWindow()
        self.setFocus()

    def check_focus(self):
        if not self.isActiveWindow() and self.isVisible():
            logger.info("視窗失去焦點，自動隱藏")
            self.hide()

    def hideEvent(self, event):
        logger.info("隱藏視窗")
        status_signal_slots.window_status = False
        logger.info(f"'status_signal_slots.window_status' has changed to {status_signal_slots.window_status}")
        event.accept()

    def closeEvent(self, event):
        logger.info("結束程式")
        self.tray_icon.hide()
        QApplication.quit()
        event.accept()

# ###########################################
# Main
# ###########################################

def app_run():
    logger.info("開始程式")
    app = QApplication([])
    window = NeverThinkAutoReply()

    logger.info("進入主事件循環")
    show_notify("NeverThinkAutoReply 已成功啟動", icon=SUCCESS_ICON)
    app.exec()
    logger.info("應用程序結束")


if __name__ == "__main__":
    app_run()
