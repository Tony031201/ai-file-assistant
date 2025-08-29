from anthropic import Anthropic
from data.meta_data import get_api

# 读取 prompt.txt
with open("./data/prompt.txt", "r", encoding="utf-8") as f:
    system_prompt = f.read()


class ClaudClient:
    def __init__(self):
        self.client = Anthropic(api_key=get_api())
        self.system_prompt = system_prompt
        self.model = "claude-3-5-haiku-20241022"
        self.tokens = 512

    def send_message(self, messages):
        response = self.client.messages.create(
            model=self.model,  # model 编号
            max_tokens=self.tokens,
            system=self.system_prompt,
            messages=[
                {"role": "user", "content": messages}
            ],
        )

        return response.content[0].text