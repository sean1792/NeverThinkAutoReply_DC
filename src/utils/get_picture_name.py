from pathlib import Path
from src.configs import WRITABLE_PATH

def get_pic_list(folder_name):
    folder_path = Path(f"{WRITABLE_PATH}/assets/{folder_name}")
    file_names = [f.name for f in folder_path.iterdir() if f.is_file()]
    return file_names

if __name__ == '__main__':
    print(get_pic_list("mygo"))
