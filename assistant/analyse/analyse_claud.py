from anthropic import Anthropic
from data.meta_data import get_api

class ClaudClient:
    def __init__(self):
        self.client = Anthropic(api_key=get_api())
        self.model = "claude-3-5-haiku-20241022"
        self.tokens = 1024

    def send_message(self, messages):
        response = self.client.messages.create(
            model=self.model,  # model 编号
            max_tokens=self.tokens,
            messages=[
                {"role": "user", "content": messages}
            ],
        )

        return response.content[0].text