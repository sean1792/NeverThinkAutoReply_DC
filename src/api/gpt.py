from openai import OpenAI
import os

from src.configs import configs, APP_ROOT_PATH
from src.utils.logger import get_logger

logger = get_logger(__name__)


class GPT:
    def __init__(self):
        logger.info("初始化 GPT 類")
        api_key = configs["Keys"].get("openai")
        if not api_key:
            logger.error("找不到 OpenAI API key")
            raise ValueError("OpenAI API key not found in config")

        self.model = configs["General"].get("gpt_model", "gpt-4o-mini")
        logger.info(f"使用模型: {self.model}")

        try:
            self.client = OpenAI(api_key=api_key)
            logger.info("OpenAI 客戶端初始化成功")
        except Exception as e:
            logger.error(f"OpenAI 客戶端初始化失敗: {str(e)}", exc_info=True)
            raise

    @staticmethod
    def _prompt_loader(method: int):
        key_map = {
            1: "normal",
            2: "refute",
            3: "toxic",
            4: "mygo"
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
                logger.debug(f"成功加載 {prompt_type} 提示詞")
                return prompt_content
        except FileNotFoundError:
            logger.error(f"找不到提示詞文件: {prompt_path}")
            raise
        except Exception as e:
            logger.error(f"讀取提示詞文件時發生錯誤: {str(e)}", exc_info=True)
            raise

    def get_response(self, prompt: str, method: int, max_tokens: int = 500, temperature: float = 0.7):
        logger.info(f"開始生成回應 (方法: {method}, 最大token: {max_tokens}, 溫度: {temperature})")
        logger.debug(f"輸入文本: {prompt[:100]}...")

        try:
            system_prompt = self._prompt_loader(method)
            logger.debug(f"系統提示詞: {system_prompt[:100]}...")

            logger.debug("發送 API 請求到 OpenAI")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature
            )

            result = response.choices[0].message.content.strip()
            logger.info("成功獲得 API 回應")
            logger.debug(f"生成的回應: {result[:100]}...")
            return result

        except Exception as e:
            raise RuntimeError(f"API 請求失敗: {str(e)}")


if __name__ == '__main__':
    try:
        logger.info("開始測試 GPT 類")
        gpt = GPT()
        prompt = """
        """
        logger.info("發送測試請求")
        reply = gpt.get_response(prompt=prompt, method=2)
        logger.info("測試完成")
        print(reply)
    except Exception as e:
        logger.error(f"測試過程中發生錯誤: {str(e)}", exc_info=True)