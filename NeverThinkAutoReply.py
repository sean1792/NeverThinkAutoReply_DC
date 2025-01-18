import os
import sys
import time
from enum import Enum, auto
import threading
from functools import partial
import asyncio

import pyperclip
import pyautogui
from pynput import keyboard
from pynput.mouse import Listener, Button

from PySide6.QtCore import Qt, QSize, QPoint, QFile, QTextStream, Signal, QObject, QTimer
from PySide6.QtGui import QCursor, QIcon
from PySide6.QtWidgets import QApplication, QHBoxLayout, QPushButton, QVBoxLayout, QWidget, QSystemTrayIcon, QMenu
from windows_toasts import WindowsToaster, Toast, ToastDisplayImage, ToastDuration

from src.api.gpt import GPT
from src.api.mygo import download_mygo, get_mygo_data
from src.utils.copy_ import copy_image
from src.configs import APP_ROOT_PATH, WRITABLE_PATH, configs
from src.utils.logger import get_logger

import logging

# ###########################################
# Notify
# ###########################################

def show_notify(text: str = "你點一下輸入框! 我來回...", icon: str = None):
    logger.info(f"顯示通知: {text}")
    toast.text_fields = [text]
    if icon:
        logger.debug(f"使用圖標: {icon}")
        toast.AddImage(ToastDisplayImage.fromPath(icon))
    toaster.show_toast(toast)

# ###########################################
# Initialize Instances
# ###########################################

logger = get_logger(__name__, logging.INFO)

HOTKEY = configs["General"].get("hotkey", "<ctrl>+<shift>+x")

toaster = WindowsToaster("NeverThinkAutoReply")
toast = Toast()
toast.duration = ToastDuration.Short

try:
    logger.info("初始化 GPT 實例")
    gpt = GPT()
except ValueError as e:
    show_notify(text=f"請至 'config.ini' 文件內 'openai' 欄位填入API Key",
                icon=os.path.join(APP_ROOT_PATH, "assets/icons/error.png"))
    sys.exit(1)
except Exception as e:
    logger.error(f"GPT 初始化失敗: {str(e)}")
    sys.exit(1)

# ###########################################
# Enums & Maps
# ###########################################

class Method(Enum):
    NORMAL = auto()
    REFUTE = auto()
    TOXIC = auto()
    MYGO = auto()


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

def process(method: Method):  # second thread
    try:
        clipboard_content = pyperclip.paste()
        logger.info(f"剪貼板內容: {clipboard_content[:100]}...")

        if not clipboard_content.strip():
            logger.warning("剪貼板是空的")
            show_notify(text="請先反白要針對回覆的內容！",
                        icon=os.path.join(APP_ROOT_PATH, "assets/icons/error.png"))
            return

        logger.info("向 GPT 發送請求")
        try:
            res = gpt.get_response(prompt=clipboard_content, method=method.value)
            logger.info(f"GPT 回應: {res[:100]}...")
        except Exception as e:
            show_notify(text=f"OpenAI API處理中發生錯誤: {str(e)}",
                        icon=os.path.join(APP_ROOT_PATH, "assets/icons/error.png"))
            return

        if method == Method.MYGO:
            try:
                logger.info("處理 Mygo 類型回應")
                mygo_data = get_mygo_data(res)
                logger.info(f"解析 Mygo 數據: {mygo_data}")

                download_path = os.path.join(WRITABLE_PATH, "downloaded")
                os.makedirs(download_path, exist_ok=True)
                file_path = os.path.join(download_path, f"{mygo_data['alt']}.jpg")

                if not os.path.exists(file_path):
                    logger.info(f"下載 Mygo 圖片: {mygo_data['alt']}")
                    download_mygo(mygo_data)
                    time.sleep(0.1)
                else:
                    logger.info("圖片已存在，跳過下載")

                logger.info(f"複製圖片到剪貼板: {file_path}")
                copy_image(file_path)
            except Exception as e:
                show_notify(text=str(e),
                            icon=os.path.join(APP_ROOT_PATH, "assets/icons/error.png"))
                return
        else:
            logger.info("複製回覆到剪貼板")
            pyperclip.copy(res)

        show_notify(text="請點擊要貼上的位置 (輸入框)",
                    icon=os.path.join(APP_ROOT_PATH, "assets/icons/success.png"))

        mouse_listener = Listener(on_click=lambda x, y, button, pressed:
                                  mouse_on_click_action(x, y, button, pressed))
        mouse_listener.start()
    finally:
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
        self.tray_icon.setIcon(QIcon(os.path.join(APP_ROOT_PATH, "assets/icons/comment.png")))

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
            return

    def on_hotkey(self):
        if (not status_signal_slots.window_status and
            not status_signal_slots.task_running.is_set()):
            logger.info("快捷鍵觸發: 顯示視窗")
            status_signal_slots.window_status = True
            logger.info(f"'status_signal_slots.window_status' has changed to {status_signal_slots.window_status}")
            self.show_below_cursor()
        else:
            logger.info("視窗已存在，忽略此次操作")

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
    app.exec()
    logger.info("應用程序結束")


if __name__ == "__main__":
    app_run()