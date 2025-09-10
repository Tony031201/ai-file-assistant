import sys
from pathlib import Path
from anthropic import Anthropic

class ClaudClient:
    def __init__(self,API_KEY:str):
        self.client = Anthropic(api_key=API_KEY)
        self.model = "claude-sonnet-4-20250514"
        self.tokens = 1024
        try:
            with open("./prompt.txt","r",encoding="utf-8") as f:
                prompt = f.read()
        except FileNotFoundError:
            print("来自项目分析模块:prompt缺失")
            sys.exit(1)
        self.prompt = prompt

    def send_message(self, file_path:Path):
        try:
            with open(file_path,"r",encoding="utf-8") as f:
                data = f.read()
        except FileNotFoundError:
            print("来自文件分析模块:文件路径不存在")
            sys.exit(1)

        response = self.client.messages.create(
            model=self.model,  # model 编号
            max_tokens=self.tokens,
            system=self.prompt,
            messages=[
                {"role": "user", "content": data}
            ],
        )

        return Path(file_path).resolve().name,response.content[0].text