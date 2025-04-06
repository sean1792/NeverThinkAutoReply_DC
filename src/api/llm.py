import os

from src.configs import configs, APP_ROOT_PATH
from src.utils.logger import get_logger
from src.utils.get_picture_name import get_pic_list

logger = get_logger(__name__)
filter_pic = []

class LLM:
    def __init__(self, base_model):
        self.base_model = base_model

        self.model = configs["Model"].get(base_model)
        logger.info(f"使用模型: {self.model}")

    @staticmethod
    def _prompt_loader(method: int):
        global filter_pic

        key_map = {
            1: "normal",
            2: "refute",
            3: "toxic",
            4: "mygo",
            5: "mujica"
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
                if prompt_type == "mygo" or prompt_type == "mujica":
                    prompt_content = prompt_content.format(
                        pics=get_pic_list(prompt_type, filter_pic)
                    )
                logger.debug(f"成功加載 {prompt_type} 提示詞")
                return prompt_content
        except FileNotFoundError:
            logger.error(f"找不到提示詞文件: {prompt_path}")
            raise
        except Exception as e:
            logger.error(f"讀取提示詞文件時發生錯誤: {str(e)}", exc_info=True)
            raise

    def get_response(self, prompt: str, method: int, max_tokens: int, temperature: float = 0.7) -> str:
        global filter_pic

        logger.info(f"開始生成回應 (方法: {method}, 最大token: {max_tokens}, 溫度: {temperature})")
        logger.debug(f"輸入文本: {prompt[:100]}...")

        try:
            system_prompt = self._prompt_loader(method)
            logger.debug(f"系統提示詞: {system_prompt[:100]}...")

            logger.debug(f"發送 API 請求到 {self.base_model}")
            response = self._gen_response(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
                temperature=temperature
            )

            result = response
            logger.info("成功獲得 API 回應")
            logger.debug(f"生成的回應: {result[:100]}...")

            if len(filter_pic) >= 10:  #回复图片不会在十次内重复出现
                filter_pic.pop(0)

            filter_pic.append(result)

            return result

        except Exception as e:
            raise RuntimeError(f"API 請求失敗: {str(e)}")


class OpenaiLLM(LLM):

    def __init__(self, base_model, base_url, api_key):
        from openai import OpenAI

        super().__init__(base_model)

        try:
            self.client = OpenAI(
                api_key=api_key, base_url=base_url if base_url != "pass" else None
            )
            logger.info(f"{self.base_model} 客戶端初始化成功")
        except Exception as e:
            logger.error(f"{self.base_model} 客戶端初始化失敗: {str(e)}", exc_info=True)
            raise

    def _gen_response(
        self, messages: list[dict], max_tokens: int, temperature: float
    ) -> str:
        return (
            self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            .choices[0]
            .message.content.strip()
        )


class HfLLM(LLM):

    def __init__(self, base_model, api_key):
        from transformers import pipeline

        super().__init__(base_model)

        try:
            self.pipeline = pipeline("text-generation", model=self.model, token=api_key)
            logger.info(f"{self.base_model} Pipeline 初始化成功")
        except Exception as e:
            logger.error(
                f"{self.base_model} Pipeline 初始化失敗: {str(e)}", exc_info=True
            )
            raise

    @staticmethod
    def _combine_system_prompt(messages: list[dict]) -> list[dict]:
        prompt_path = os.path.join(
            APP_ROOT_PATH, f"assets/prompts/without_system_prompt.txt"
        )
        logger.debug(f"合併系統提示詞: {prompt_path}")

        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                prompt_content = f.read().strip()
                prompt_content = prompt_content.format(
                    system_prompt=messages[0]["content"], prompt=messages[1]["content"]
                )
                logger.debug(f"成功合併系統提示詞")
        except FileNotFoundError:
            logger.error(f"找不到提示詞文件: {prompt_path}")
            raise
        except Exception as e:
            logger.error(f"讀取提示詞文件時發生錯誤: {str(e)}", exc_info=True)
            raise

        result = [{"role": "user", "content": prompt_content}]
        return result

    def _gen_response(
        self, messages: list[dict], max_tokens: int, temperature: float
    ) -> str:
        from jinja2.exceptions import TemplateError

        do_sample = temperature != 1.0
        try:
            response = self.pipeline(
                messages,
                max_new_tokens=max_tokens,
                do_sample=do_sample,
                temperature=temperature,
            )
        except TemplateError as e:
            messages = self._combine_system_prompt(messages)
            response = self.pipeline(
                messages,
                max_new_tokens=max_tokens,
                do_sample=do_sample,
                temperature=temperature,
            )
        return response[0]["generated_text"][-1]["content"].strip()


def get_llm(base_model) -> LLM:
    logger.info("初始化 LLM")

    base_url = configs["BaseURL"].get(base_model)
    api_key = configs["Keys"].get(base_model)
    if not api_key:
        logger.error(f"找不到 {base_model} 的 API key")
        raise ValueError(f"{base_model} API key not found in config")

    if base_model == "hugging_face":
        return HfLLM(base_model, api_key)
    else:
        return OpenaiLLM(base_model, base_url, api_key)
