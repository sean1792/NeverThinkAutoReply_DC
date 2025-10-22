from openai import OpenAI
import os
import json

from src.configs import configs, APP_ROOT_PATH
from src.utils.logger import get_logger
from src.utils.get_picture_name import get_pic_list

logger = get_logger(__name__)
filter_pic = []


class LLM:
    def __init__(self, base_model):
        logger.info("初始化 LLM 類")
        self.base_model = base_model
        base_url = configs["BaseURL"].get(base_model)
        api_key = configs["Keys"].get(base_model)
        # if not api_key:
        #     logger.error(f"找不到 {base_model} 的 API key")
        #     raise ValueError(f"{base_model} API key not found in config")

        self.model = configs["Model"].get(base_model)
        # self.model = "gemini-2.0-flash"
        logger.info(f"使用模型: {self.model}")

        try:
            self.client = OpenAI(api_key=api_key,
                                 base_url=base_url if base_url != "pass" else None)
            # self.client = OpenAI(api_key="ss",
            #                      base_url="http://192.168.88.110:32770/v1")
            # self.client = OpenAI(api_key="zu-96e988656dcd51a6caee1738e9affc4b",
            #                      base_url="https://api.zukijourney.com/v1")
            logger.info(f"{base_model} 客戶端初始化成功")
        except Exception as e:
            logger.error(f"{base_model} 客戶端初始化失敗: {str(e)}", exc_info=True)
            raise

    @staticmethod
    def _prompt_loader(method: int):
        global filter_pic

        key_map = {
            0: "mujica_all_json",
            1: "mujica_all2",
        }

        prompt_type = key_map.get(method)
        if not prompt_type:
            logger.error(f"無效的方法類型: {method}")
            raise ValueError(f"Invalid method type: {method}")

        prompt_path = os.path.join(APP_ROOT_PATH, f"assets/prompts/{prompt_type}.txt")
        logger.debug(f"加載提示詞文件: {prompt_path}")

        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                prompt_content = f.read().strip()
                prompt_content = prompt_content.format(pics=get_pic_list("mujica_all", filter_pic=filter_pic))
                logger.debug(f"成功加載 {prompt_type} 提示詞")
                return prompt_content
        except FileNotFoundError:
            logger.error(f"找不到提示詞文件: {prompt_path}")
            raise
        except Exception as e:
            logger.error(f"讀取提示詞文件時發生錯誤: {str(e)}", exc_info=True)
            raise

    def get_response(self,
                     prompt: str,
                     method: int,
                     max_tokens: int = 500,
                     temperature: float = 0.7,
                     two_step: bool = False,
                     pic_filter: bool = False):
        global filter_pic

        logger.info(f"開始生成回應 (最大token: {max_tokens}, 溫度: {temperature})")
        logger.debug(f"輸入文本: {prompt[:100]}...")

        try:
            if not two_step:
                system_prompt = self._prompt_loader(method)
                # print(system_prompt)
                logger.debug(f"系統提示詞: {system_prompt[:100]}...")

                logger.debug(f"發送 API 請求到 {self.base_model}")

                response = self.client.chat.completions.create(
                    model=self.model,
                    # model="gpt-4o",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                jsondata = json.loads(response.choices[0].message.content)
                logger.info(jsondata)
                if type(jsondata) is list:
                    result = jsondata[0]["meme_file"]
                else:
                    result = jsondata["meme_file"]

            else:  # for two step scenario

                response = self.client.chat.completions.create(
                    # model=self.model,
                    # model="tulu-3-405b",
                    model="gemini-1.5-flash",
                    messages=[
                        {"role": "system", "content": "你要扮演一個話不多的網路酸民，你只會用最簡短的幾個字來做出一針見血的回應"},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=10,
                    temperature=0.7
                )
                print(response)
                a = f"他說:{prompt}\n你說:{response.choices[0].message.content}"
                print(a)

                # 2 stage generate
                response = self.client.chat.completions.create(
                    # model=self.model,
                    model="gemini-1.5-flash",
                    # model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": a}
                    ],
                    max_tokens=max_tokens,
                    temperature=0
                )
                print(response)

                result = response.choices[0].message.content.strip()
            logger.info("成功獲得 API 回應")
            logger.debug(f"生成的回應: {result[:100]}...")

            if pic_filter is True:
                if len(filter_pic) >= 10:  # 回复图片不会在十次内重复出现
                    filter_pic.pop(0)

                filter_pic.append(result)

            return result

        except Exception as e:
            raise RuntimeError(f"API 請求失敗: {str(e)}")
