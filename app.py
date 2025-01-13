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
from PySide6.QtCore import Qt, QSize, QPoint, QTimer, QFile, QTextStream, Signal, QObject
from PySide6.QtGui import QMouseEvent, QCursor, QIcon
from PySide6.QtWidgets import QApplication, QHBoxLayout, QPushButton, QVBoxLayout, QWidget, QSystemTrayIcon, QMenu
from windows_toasts import WindowsToaster, Toast, ToastDisplayImage, ToastDuration

from src.api.gpt import GPT
from src.api.mygo import download_mygo, get_mygo_data
from src.utils.copy_ import copy_image
from src.configs import APP_ROOT_PATH, WRITABLE_PATH, configs
from src.utils.logger import get_logger

logger = get_logger(__name__)


def show_notify(text: str = "你點一下輸入框! 我來回...", icon: str = None):
    logger.debug(f"顯示通知: {text}")
    toast.text_fields = [text]
    if icon:
        logger.debug(f"使用圖標: {icon}")
        toast.AddImage(ToastDisplayImage.fromPath(icon))
    toaster.show_toast(toast)


try:
    logger.info("初始化 GPT 實例")
    gpt = GPT()
except Exception as e:
    logger.error(f"GPT 初始化失敗: {str(e)}")
    show_notify(text=str(e),
                icon=os.path.join(APP_ROOT_PATH, "assets/icons/error.png"))
    sys.exit(1)

logger.info(f"設置快捷鍵: {configs['General'].get('hotkey', 'ctrl+shift+x')}")
is_processing = False
HOTKEY = configs["General"].get("hotkey", "ctrl+shift+x")


class HotkeySignals(QObject):
    triggered = Signal()


class HotkeyListener:
    def __init__(self):
        logger.info("初始化快捷鍵監聽器")
        self.signals = HotkeySignals()

    def start(self):
        logger.info(f"啟動快捷鍵監聽: {HOTKEY}")
        keyboard.add_hotkey(HOTKEY, self.on_hotkey)

    def stop(self):
        logger.info("停止快捷鍵監聽")
        keyboard.remove_hotkey(HOTKEY)

    def on_hotkey(self):
        if not is_processing:
            logger.debug("觸發快捷鍵，執行複製操作")
            time.sleep(0.5)
            pyautogui.hotkey('ctrl', 'c')
            time.sleep(0.5)
            self.signals.triggered.emit()


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

logger.info("初始化 Windows 通知系統")
toaster = WindowsToaster("AutoReply")
toast = Toast()
toast.duration = ToastDuration.Short


class MouseClickListener:
    def __init__(self):
        logger.info("初始化滑鼠點擊監聽器")
        self.listener = None
        self.is_listening = False

    def start_listening(self, callback):
        if not self.is_listening:
            logger.debug("啟動滑鼠點擊監聽")
            self.is_listening = True
            self.listener = Listener(on_click=lambda x, y, button, pressed:
            self.on_click(x, y, button, pressed, callback))
            self.listener.start()

    def stop_listening(self):
        if self.listener:
            logger.debug("停止滑鼠點擊監聽")
            self.is_listening = False
            self.listener.stop()
            self.listener = None

    def on_click(self, x, y, button, pressed, callback):
        if pressed and self.is_listening:
            logger.debug(f"檢測到滑鼠點擊: 座標({x}, {y})")
            time.sleep(0.5)
            pyautogui.hotkey('ctrl', 'v')
            self.stop_listening()
            callback()
            return False


mouse_listener = MouseClickListener()


def process(method: Method, window):
    global is_processing
    try:
        if is_processing:
            logger.warning("已有處理中的任務")
            show_notify(text="正在處理中，請稍候...")
            return

        logger.info(f"開始處理 {method.name} 類型的請求")
        is_processing = True
        window.setEnabled(False)

        clipboard_content = pyperclip.paste()
        logger.debug(f"獲取剪貼板內容: {clipboard_content[:100]}...")

        if not clipboard_content.strip():
            logger.warning("剪貼板內容為空")
            show_notify(text="請先複製要處理的文字！",
                        icon=os.path.join(APP_ROOT_PATH, "assets/icons/error.png"))
            is_processing = False
            window.setEnabled(True)
            return

        logger.info("向 GPT 發送請求")
        res = gpt.get_response(prompt=clipboard_content, method=method.value)
        logger.debug(f"GPT 回應: {res[:100]}...")

        if method == Method.MYGO:
            logger.info("處理 Mygo 類型回應")
            mygo_data = get_mygo_data(res)
            logger.debug(f"解析 Mygo 數據: {mygo_data}")

            download_path = os.path.join(WRITABLE_PATH, "downloaded")
            os.makedirs(download_path, exist_ok=True)
            file_path = os.path.join(download_path, f"{mygo_data['alt']}.jpg")

            if not os.path.exists(file_path):
                logger.info(f"下載 Mygo 圖片: {mygo_data['alt']}")
                download_mygo(mygo_data)
                time.sleep(0.1)
            else:
                logger.debug("圖片已存在，跳過下載")

            logger.debug(f"複製圖片到剪貼板: {file_path}")
            copy_image(file_path)
        else:
            logger.debug("複製回應到剪貼板")
            pyperclip.copy(res)

        show_notify(icon=METHODS[method].get("icon", None))

        def after_paste():
            global is_processing
            logger.info("完成處理，重置狀態")
            is_processing = False
            window.setEnabled(True)
            window.hide()

        logger.debug("等待使用者點擊貼上位置")
        mouse_listener.start_listening(after_paste)

    except Exception as e:
        logger.error(f"處理過程發生錯誤: {str(e)}", exc_info=True)
        show_notify(text="發生錯誤: " + str(e),
                    icon=os.path.join(APP_ROOT_PATH, "assets/icons/error.png"))
        is_processing = False
        window.setEnabled(True)


def start_thread(method: Method, window):
    logger.debug(f"啟動新線程處理 {method.name} 請求")
    threading.Thread(target=lambda: process(method, window),
                     daemon=True).start()


class QuickReply(QWidget):
    def __init__(self):
        super().__init__()
        logger.info("初始化 QuickReply 視窗")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.init_ui()
        self._is_dragging = False
        self._start_pos = None
        self.hide_timer = QTimer(self)
        self.hide_timer.timeout.connect(self.check_focus)
        self.hide_timer.start(500)

        logger.info("初始化系統托盤")
        self.init_tray()

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
        quit_action.triggered.connect(QApplication.quit)

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
            logger.debug("快捷鍵觸發: 隱藏視窗")
            self.hide()
        else:
            logger.debug("快捷鍵觸發: 顯示視窗")
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
        logger.debug(f"在游標位置下方顯示視窗: {cursor_pos.x()}, {cursor_pos.y()}")
        self.move(cursor_pos + QPoint(0, 20))
        self.show()
        self.activateWindow()
        self.setFocus()

    def check_focus(self):
        if not is_processing and not self.isActiveWindow() and self.isVisible():
            logger.debug("視窗失去焦點，自動隱藏")
            self.hide()

    def closeEvent(self, event):
        logger.debug("攔截關閉事件，改為隱藏視窗")
        event.ignore()
        self.hide()


def app_run():
    logger.info("啟動應用程序")
    app = QApplication([])
    window = QuickReply()

    logger.info("進入主事件循環")
    app.exec()
    logger.info("應用程序結束")


if __name__ == "__main__":
    app_run()