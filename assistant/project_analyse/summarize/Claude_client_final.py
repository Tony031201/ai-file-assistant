import sys,json
from pathlib import Path
from anthropic import Anthropic

class ClaudClient2:
    def __init__(self,API_KEY:str):
        self.client = Anthropic(api_key=API_KEY)
        self.model = "claude-sonnet-4-20250514"
        self.tokens = 2048
        try:
            with open("./summarize/prompt.txt", "r", encoding="utf-8") as f:
                prompt = f.read()
        except FileNotFoundError:
            print("来自项目分析模块:prompt2缺失")
            sys.exit(1)
        self.prompt = prompt

    def send_message(self, data):

        response = self.client.messages.create(
            model=self.model,  # model 编号
            max_tokens=self.tokens,
            system=self.prompt,
            messages=[
                {"role": "user", "content": json.dumps(data, ensure_ascii=False)}
            ],
        )

        return response.content[0].text