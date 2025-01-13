from openai import OpenAI
import os

from src.configs import configs, APP_ROOT_PATH


class GPT:
    def __init__(self):
        self.client = OpenAI(api_key=configs["Keys"].get("openai"))
        self.model = configs["General"].get("gpt_model", "gpt-4o-mini")

    @staticmethod
    def _prompt_loader(method: int):
        key_map = {
            1: "normal",
            2: "refute",
            3: "toxic",
            4: "mygo"
        }
        with open(os.path.join(APP_ROOT_PATH, f"assets/prompts/{key_map[method]}.txt"),
                  "r", encoding="utf-8") as f:
            return f.read().strip()

    def get_response(self, prompt: str, method: int, max_tokens: int = 500, temperature: float = 0.7):
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._prompt_loader(method)},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"Error: {str(e)}"


if __name__ == '__main__':
    gpt = GPT()
    prompt = """
    """
    reply = gpt.get_response(prompt=prompt, method=2)
    print(reply)