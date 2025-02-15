import configparser
import os
import sys

def _read_config():
    config = configparser.ConfigParser()
    config.read(os.path.join(WRITABLE_PATH, "config.ini"), encoding="utf-8")

    config_data = {}

    for section in config.sections():
        config_data[section] = {}
        for key, value in config.items(section):
            config_data[section][key] = value

    return config_data

def _get_application_root_path():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    else:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _get_writable_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


APP_ROOT_PATH = _get_application_root_path()
WRITABLE_PATH = _get_writable_path()
configs = _read_config()
