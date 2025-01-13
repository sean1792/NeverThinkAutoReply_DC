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


def show_notify(text: str = "你點一下輸入框! 我來回...", icon: str = None):
    toast.text_fields = [text]
    if icon:
        toast.AddImage(ToastDisplayImage.fromPath(icon))
    toaster.show_toast(toast)


try:
    gpt = GPT()
except Exception as e:
    show_notify(text=str(e),
                icon=os.path.join(APP_ROOT_PATH, "assets/icons/error.png"))
    sys.exit(1)


is_processing = False
HOTKEY = configs["General"].get("hotkey", "ctrl+shift+x")


class HotkeySignals(QObject):
    triggered = Signal()


class HotkeyListener:
    def __init__(self):
        self.signals = HotkeySignals()

    def start(self):
        keyboard.add_hotkey(HOTKEY, self.on_hotkey)

    def stop(self):
        keyboard.remove_hotkey(HOTKEY)

    def on_hotkey(self):
        if not is_processing:
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

toaster = WindowsToaster("AutoReply")
toast = Toast()
toast.duration = ToastDuration.Short


class MouseClickListener:
    def __init__(self):
        self.listener = None
        self.is_listening = False

    def start_listening(self, callback):
        if not self.is_listening:
            self.is_listening = True
            self.listener = Listener(on_click=lambda x, y, button, pressed:
            self.on_click(x, y, button, pressed, callback))
            self.listener.start()

    def stop_listening(self):
        if self.listener:
            self.is_listening = False
            self.listener.stop()
            self.listener = None

    def on_click(self, x, y, button, pressed, callback):
        if pressed and self.is_listening:
            print("滑鼠點擊位置：", x, y)
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
            show_notify(text="正在處理中，請稍候...")
            return

        is_processing = True
        window.setEnabled(False)


        clipboard_content = pyperclip.paste()
        print(f"剪貼版有: {clipboard_content}")

        if not clipboard_content.strip():
            show_notify(text="請先複製要處理的文字！",
                        icon=os.path.join(APP_ROOT_PATH, "assets/icons/error.png"))
            is_processing = False
            window.setEnabled(True)
            return

        res = gpt.get_response(prompt=clipboard_content, method=method.value)
        print(f"GPT回覆: {res}")

        if method == Method.MYGO:
            mygo_data = get_mygo_data(res)
            print(f"Mygo data: {mygo_data}")
            os.makedirs(os.path.join(WRITABLE_PATH, "downloaded"), exist_ok=True)
            if not os.path.exists(os.path.join(WRITABLE_PATH, "downloaded", f"{mygo_data['alt']}.jpg")):
                download_mygo(mygo_data)
                time.sleep(0.1)
            copy_image(os.path.join(WRITABLE_PATH, "downloaded", f"{mygo_data['alt']}.jpg"))
        else:
            pyperclip.copy(res)

        show_notify(icon=METHODS[method].get("icon", None))

        def after_paste():
            global is_processing
            is_processing = False
            window.setEnabled(True)
            # window.activateWindow()
            window.hide()
        mouse_listener.start_listening(after_paste)

    except Exception as e:
        show_notify(text="發生錯誤: " + str(e),
                    icon=os.path.join(APP_ROOT_PATH, "assets/icons/error.png"))
        is_processing = False
        window.setEnabled(True)


def start_thread(method: Method, window):
    threading.Thread(target=lambda: process(method, window),
                     daemon=True).start()


class QuickReply(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.init_ui()
        self._is_dragging = False
        self._start_pos = None
        self.hide_timer = QTimer(self)
        self.hide_timer.timeout.connect(self.check_focus)
        self.hide_timer.start(500)

        self.init_tray()

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

        self.tray_icon.setToolTip(f"QuickReply (快捷鍵: {HOTKEY})")

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
                partial(start_thread, btn_info["type"], self))
            button.setFixedSize(QSize(120, 40))
            menu_layout.addWidget(button)

        main_layout.addWidget(self.menu_widget)
        self.setLayout(main_layout)
        self.resize(500, 50)
        self.load_style_sheet()

    def on_hotkey(self):
        if self.isVisible():
            self.hide()
        else:
            self.show_below_cursor()

    def load_style_sheet(self):
        file = QFile(os.path.join(APP_ROOT_PATH, "assets/stylesheets/style.qss"))
        if file.open(QFile.ReadOnly | QFile.Text):
            stream = QTextStream(file)
            style = stream.readAll()
            self.setStyleSheet(style)
        file.close()

    def show_below_cursor(self):
        cursor_pos = QCursor.pos()
        self.move(cursor_pos + QPoint(0, 20))
        self.show()
        self.activateWindow()
        self.setFocus()

    def check_focus(self):
        if not is_processing and not self.isActiveWindow() and self.isVisible():
            self.hide()

    def closeEvent(self, event):
        event.ignore()
        self.hide()


def app_run():
    app = QApplication([])
    window = QuickReply()

    app.exec()


if __name__ == "__main__":
    app_run()