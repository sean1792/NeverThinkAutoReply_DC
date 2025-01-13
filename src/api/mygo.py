import json
import os
import time

import requests

from src.configs import configs, WRITABLE_PATH


def get_mygo_data(key: str):
    return json.loads(requests.get(configs["API"].get("mygo").format(key=key)).content.decode("utf-8"))["urls"][0]

def download_mygo(data: dict):
    target_path = os.path.join(WRITABLE_PATH, "downloaded")
    try:
        target_path = os.path.join(target_path, f"{data['alt']}.jpg")
        response = requests.get(data["url"], stream=True)
        response.raise_for_status()
        with open(target_path, 'wb') as file:
            for chunk in response.iter_content(1024):
                file.write(chunk)
        print(f"圖片已成功下載並保存到 {target_path}")
        return True
    except Exception as e:
        print(f"下載圖片時發生錯誤: {e}")
        return False


if __name__ == '__main__':
    data = get_mygo_data("")
    print(data)
    download_mygo(data)
