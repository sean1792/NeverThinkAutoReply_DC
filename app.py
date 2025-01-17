import os
import sys
import time
from enum import Enum, auto
import threading
from functools import partial

import keyboard
import pyperclip
import pyautogui
from pynput.mouse import Listener
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

logger = get_logger(__name__, logging.INFO)

processing_lock = threading.Lock()
is_processing = False

logger.info(f"設置快捷鍵: {configs['General'].get('hotkey', 'ctrl+shift+x')}")
HOTKEY = configs["General"].get("hotkey", "ctrl+shift+x")

logger.info("初始化 Windows 通知系統")
toaster = WindowsToaster("AutoReply")
toast = Toast()
toast.duration = ToastDuration.Short

def show_notify(text: str = "你點一下輸入框! 我來回...", icon: str = None):
    logger.info(f"顯示通知: {text}")
    toast.text_fields = [text]
    if icon:
        logger.debug(f"使用圖標: {icon}")
        toast.AddImage(ToastDisplayImage.fromPath(icon))
    toaster.show_toast(toast)

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


def get_processing_state() -> bool:
    with processing_lock:
        return is_processing

def set_processing_state(state: bool) -> None:
    global is_processing
    with processing_lock:
        is_processing = state


class Method(Enum):
    NORMAL = auto()
    REFUTE = auto()
    TOXIC = auto()
    MYGO = auto()


METHODS = {
    Method.NORMAL: {
        "icon": os.path.join(APP_ROOT_PATH, "assets/icons/comment.png"),
        "text": "正常回覆",
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
        "text": "Mygo",
        "type": Method.MYGO,
    }
}


class HotkeySignals(QObject):
    triggered = Signal()


class HotkeyListener:
    def __init__(self):
        logger.info("初始化快捷鍵監聽器")
        self.signals = HotkeySignals()
        self.is_listening = False
        self._lock = threading.Lock()

    def start(self):
        logger.info(f"啟動快捷鍵監聽: {HOTKEY}")
        with self._lock:
            if not self.is_listening:
                keyboard.add_hotkey(HOTKEY, self.on_hotkey)
                self.is_listening = True

    def stop(self):
        logger.info("停止快捷鍵監聽")
        with self._lock:
            if self.is_listening:
                keyboard.remove_hotkey(HOTKEY)
                self.is_listening = False

    def on_hotkey(self):
        if not is_processing:
            logger.info("觸發快捷鍵，執行複製操作")
            time.sleep(0.5)
            pyautogui.hotkey('ctrl', 'c')
            time.sleep(0.5)
            self.signals.triggered.emit()

def paste_from_cp():
    time.sleep(0.5)
    pyautogui.hotkey('ctrl', 'v')

class MouseClickListener:
    def __init__(self):
        logger.info("初始化滑鼠點擊監聽器")
        self.listener = None
        self.is_listening = False

    def start_listening(self, callback):
        if not self.is_listening:
            logger.info("啟動滑鼠點擊監聽")
            self.is_listening = True
            self.listener = Listener(on_click=lambda x, y, button, pressed:
            self.on_click(x, y, button, pressed, callback))
            self.listener.start()

    def stop_listening(self):
        if self.listener:
            logger.info("停止滑鼠點擊監聽")
            self.is_listening = False
            self.listener.stop()
            self.listener = None

    def on_click(self, x, y, button, pressed, callback):
        try:
            if pressed and self.is_listening:
                logger.info(f"檢測到滑鼠點擊: 座標({x}, {y})")
                
                temp_thread = threading.Thread(target=paste_from_cp, daemon=True)
                temp_thread.start()
                
                self.stop_listening()
                callback()
                return False
        except Exception as e:
            logger.error(f"處理滑鼠點擊事件時發生錯誤: {str(e)}", exc_info=True)
            show_notify(text=f"處理滑鼠點擊事件時發生錯誤: {str(e)}",
                        icon=os.path.join(APP_ROOT_PATH, "assets/icons/error.png"))
            self.stop_listening()

mouse_listener = MouseClickListener()


def process(method: Method, window):
    try:
        if get_processing_state():
            show_notify(text="正在處理中，請稍候...")
            return

        set_processing_state(True)
        window.setEnabled(False)

        clipboard_content = pyperclip.paste()
        logger.info(f"獲取剪貼板內容: {clipboard_content[:100]}...")

        if not clipboard_content.strip():
            logger.warning("剪貼板內容為空")
            show_notify(text="請先複製要處理的文字！",
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
            logger.info("複製回應到剪貼板")
            pyperclip.copy(res)

        show_notify(icon=METHODS[method].get("icon", None))

        def after_paste():
            logger.info("process正常完成處理")

        logger.info("等待使用者點擊貼上位置")
        mouse_listener.start_listening(after_paste)
    except Exception as e:
        logger.error(f"處理過程發生錯誤: {str(e)}", exc_info=True)
        show_notify(text=f"發生錯誤: {str(e)}",
                    icon=os.path.join(APP_ROOT_PATH, "assets/icons/error.png"))
        return
    finally:
        logger.info("process結束 清除狀態")
        set_processing_state(False)
        window.setEnabled(True)
        window.hide()


def start_thread(method: Method, window):
    logger.info(f"啟動新線程處理 {method.name} 請求")
    thread = threading.Thread(target=lambda: process(method, window), daemon=True)
    window.active_threads.append(thread)
    thread.start()

# def start_mouseListen_thread(winodw):
#     logger.info(f"啟動新線程處理 滑鼠 請求")
#     thread = threading.Thread(target=lambda: process(method, window), daemon=True)
#     window.active_threads.append(thread)
#     thread.start()


class QuickReply(QWidget):
    def __init__(self):
        super().__init__()
        logger.info("初始化 QuickReply 視窗")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self.hide_timer = QTimer(self)
        self.hide_timer.timeout.connect(self.check_focus)
        self.hide_timer.start(100)

        self.init_ui()

        self.active_threads: list[threading.Thread] = []
        self._thread_lock = threading.Lock()

        self.init_tray()

        self.setup_hotkey_listener()

    def setup_hotkey_listener(self):
        logger.info("設置快捷鍵監聽")
        self.hotkey_listener = HotkeyListener()
        self.hotkey_listener.signals.triggered.connect(self.on_hotkey)
        self.hotkey_listener.start()

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
        logger.debug(f"設置系統托盤提示: QuickReply (快捷鍵: {HOTKEY})")
        self.tray_icon.setToolTip(f"QuickReply (快捷鍵: {HOTKEY})")

    def init_ui(self):
        logger.debug("初始化用戶界面")
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
                partial(start_thread, btn_info["type"], self))
            button.setFixedSize(QSize(120, 40))
            menu_layout.addWidget(button)

        main_layout.addWidget(self.menu_widget)
        self.setLayout(main_layout)
        self.resize(500, 50)
        self.load_style_sheet()

    def on_hotkey(self):
        if self.isVisible():
            logger.info("快捷鍵觸發: 隱藏視窗")
            self.hide()
        else:
            logger.info("快捷鍵觸發: 顯示視窗")
            self.show_below_cursor()

    def load_style_sheet(self):
        logger.debug("加載樣式表")
        style_path = os.path.join(APP_ROOT_PATH, "assets/stylesheets/style.qss")
        file = QFile(style_path)
        if file.open(QFile.ReadOnly | QFile.Text):
            stream = QTextStream(file)
            style = stream.readAll()
            self.setStyleSheet(style)
        file.close()

    def show_below_cursor(self):
        cursor_pos = QCursor.pos()
        logger.info(f"在游標位置下方顯示視窗: {cursor_pos.x()}, {cursor_pos.y()}")
        self.move(cursor_pos + QPoint(0, 20))
        self.show()
        self.activateWindow()
        self.setFocus()

        if not self.hotkey_listener.is_listening:
            self.hotkey_listener.start()

    def check_focus(self):
        if not is_processing and not self.isActiveWindow() and self.isVisible():
            logger.info("視窗失去焦點，自動隱藏")
            self.hide()
    # overload
    def closeEvent(self, event):
        self.hotkey_listener.stop()
        mouse_listener.stop_listening()

        with self._thread_lock:
            for thread in self.active_threads:
                if thread.is_alive():
                    thread.join(timeout=1.0)
            self.active_threads.clear()

        logger.info("結束程式")
        self.tray_icon.hide()
        QApplication.quit()
        event.accept()


def app_run():
    logger.info("啟動應用程序")
    app = QApplication([])
    window = QuickReply()

    logger.info("進入主事件循環")
    app.exec()
    logger.info("應用程序結束")


if __name__ == "__main__":
    app_run()