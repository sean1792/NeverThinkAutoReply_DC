import easyocr

from src.configs import configs

lang_map = {
    'zh-cn': 'ch_sim',
    'zh-tw': 'ch_tra',
}

lang_cfg = configs["General"].get("ocr_lang", "zh-tw")
lang = lang_map[lang_cfg]

if __name__ == '__main__':
    try:
        print(f"正在下載 OCR 語言包 : {lang_cfg}")
        easyocr.Reader([lang])
    finally:
        print("OCR 語言包下載完成")
