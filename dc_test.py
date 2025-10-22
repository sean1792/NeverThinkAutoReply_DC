import discord
from discord.ext import commands
from src.api.llm_d import LLM
from src.configs import APP_ROOT_PATH, WRITABLE_PATH, configs
from src.utils.logger import get_logger
import logging
from enum import Enum, auto
import os
import glob

# 設定 Intents
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True  # 需要啟用此選項來讀取訊息

# 機器人前綴（這裡不用，因為我們用提及來觸發）
bot = commands.Bot(command_prefix="!", intents=intents)

# logger = get_logger(__name__, logging.INFO)
# logger.info(f"使用模型")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

logger.info("Discord Bot 正在啟動...")


BASE_MODEL = configs["General"].get("base_model", "openai")
# method = METHODS.values()[0]
# print(method)
mygo_or_mujica = "mygo"
# print(METHODS.values(0))
try:
    llm = LLM(BASE_MODEL)
except ValueError as e:
    logger.info(f"請至 'config.ini' 文件內的[Keys] '{BASE_MODEL}' 欄位填入API Key",
                )
    # sys.exit(1)
except Exception as e:
    print(f"LLM 初始化失敗: {str(e)}")
    # sys.exit(1)

@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user}')

@bot.event
async def on_message(message):
    # 確保機器人不回應自己的訊息
    if message.author == bot.user:
        return

    # 檢查機器人是否被提及
    if bot.user in message.mentions and not message.mention_everyone:
        # 檢查是否是"回覆某則訊息"時提及機器人
        if message.reference:
            try:
                # 獲取被回覆的訊息
                replied_message = await message.channel.fetch_message(message.reference.message_id)
                replied_content = replied_message.content
                logger.info(f"使用者回覆的訊息內容: {replied_content}")
                try:
                    res = llm.get_response(prompt=replied_content, method=0) # 4: mygo 5: mujica 6: mygo + mujica
                    logger.info(f"{BASE_MODEL} 回應: {res[:100]}...")
                except Exception as e:
                    logger.info(f"{BASE_MODEL} API 處理中發生錯誤: {str(e)}",
                                )
                try:
                    logger.info("處理 MyGo / Ave Mujica 類型回應")
    
                    # file_path = os.path.join(WRITABLE_PATH, "assets", mygo_or_mujica, res)
                    # if not os.path.exists(file_path):
                    # print(res+".jpg")
                    res = res.split(".")[0]
                    file_path = os.path.join(WRITABLE_PATH, "assets", "mujica_all", "*"+glob.escape(res))
                    print(file_path)
                    file_path_glob = glob.glob(file_path+"*")
                    file_path = file_path_glob[0]
    
                    if not os.path.exists(file_path):
                        # file_path = os.path.join(WRITABLE_PATH, "assets", "mujica_all", res+".JPG")
                        # if not os.path.exists(file_path):
                        raise FileNotFoundError(f"找不到圖片名: {res}, 路徑: {file_path}")
    
                    logger.info(f"複製圖片到剪貼板: {file_path}")
                    # copy_image(file_path)
                    file = discord.File(file_path, filename="image.jpg")
                    # await ctx.send("這是一張測試圖片", file=file)
                    # await message.channel.send(f"你回覆的內容是: {replied_content}",file=file)
                    await message.channel.send(file=file)
                except Exception as e:
                    logger.error(str(e)
                                )
                    # 重試
                    try:
                        res = llm.get_response(prompt=replied_content, method=0) # 4: mygo 5: mujica 6: mygo + mujica
                        logger.info(f"{BASE_MODEL} 回應: {res[:100]}...")
                    except Exception as e:
                        logger.info(f"{BASE_MODEL} API 處理中發生錯誤: {str(e)}",
                                    )
                    try:
                        logger.info("處理 MyGo / Ave Mujica 類型回應")
        
                        # file_path = os.path.join(WRITABLE_PATH, "assets", mygo_or_mujica, res)
                        # if not os.path.exists(file_path):
                        # print(res+".jpg")
                        res = res.split(".")[0]
                        file_path = os.path.join(WRITABLE_PATH, "assets", "mujica_all", "*"+glob.escape(res))
                        print(file_path)
                        file_path_glob = glob.glob(file_path+"*")
                        file_path = file_path_glob[0]
        
                        if not os.path.exists(file_path):
                            # file_path = os.path.join(WRITABLE_PATH, "assets", "mujica_all", res+".JPG")
                            # if not os.path.exists(file_path):
                            raise FileNotFoundError(f"找不到圖片名: {res}, 路徑: {file_path}")
        
                        logger.info(f"複製圖片到剪貼板: {file_path}")
                        # copy_image(file_path)
                        file = discord.File(file_path, filename="image.jpg")
                        # await ctx.send("這是一張測試圖片", file=file)
                        # await message.channel.send(f"你回覆的內容是: {replied_content}",file=file)
                        await message.channel.send(file=file)
                    except Exception as e:
                        logger.error(str(e)
                                    )

                # 讓機器人回應該內容
                # await message.channel.send(f"你回覆的內容是: {replied_content}")

            except discord.NotFound:
                logger.warning("找不到被回覆的訊息，可能已被刪除。")
                await message.channel.send("無法取得被回覆的訊息，可能已被刪除。")

            except discord.Forbidden:
                logger.warning("機器人沒有權限讀取該訊息。")
                await message.channel.send("我沒有權限讀取該訊息。")

            except discord.HTTPException as e:
                logger.error(f"獲取被回覆的訊息時發生錯誤: {e}")
                await message.channel.send("無法取得被回覆的訊息，發生錯誤。")

        else:
            # 如果沒有回覆訊息，只是單純@機器人
            await message.channel.send(f'嗨 {message.author.mention}，你提到我了！')

# 你的 bot token
TOKEN = ""
bot.run(TOKEN)
