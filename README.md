# Never Think Auto Reply Discord bot


### 自動MyGo、Ave Mujica、正常、反駁、嘲諷，全程無需使用者動腦
### 基於 https://github.com/RyuuMeow/NeverThinkAutoReply 做的dc bot
### 預設使用gemini

## 前置需求
1. 取得DC的機器人token
2. 取得openai、gemini等大語言模型的apikey

## 用法
1. docker 安裝
- 下載
```bash
docker pull sean1792/ntar_dc:latest
```
- 執行
```bash
docker run --env-file .env sean1792/ntar_dc
```
> [!NOTE]
> 在.env中寫入API_KEY、TOKEN
```bash
API_KEY=xxxxxx
TOKEN=xxxxxx
```

2. 直接使用
- 將apikey以及dc token寫入環境變數API_KEY、TOKEN
- 或是直接修改dc_test.py中的token以及llm_d.py中的apikey
- 執行 dc_test.py


## 自己加圖片

將圖片丟至 `assets/mujica_all` 底下

## 修改prompt
修改 `assets/mujica_all_json.txt` 的內容 


---

## 系統需求

- 作業系統：Windows 10+

  或

- Python 3.9+



## 圖片來源

- https://github.com/serser322/ave-mujica-images
