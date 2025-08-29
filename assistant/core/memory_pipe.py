from typing import TypedDict

# ai的记忆能力, Memory_Pipe为 最大记忆储存管道, memory_number为记忆对话最大轮数
class Message(TypedDict):
    role: str
    content: str

class Memory_Pipe:
    def __init__(self,memory_number:int):
        self.memory: list[Message] = []
        self.memory_number = memory_number

    def _push(self, message: Message):
        if not isinstance(message['role'], str) or not isinstance(message['content'], str):
            raise TypeError('Role and Content must be strings')
        self.memory.append(message)

    def _pop(self):
        return self.memory.pop(0)

    def process(self,message:Message):
        self._push(message)
        if len(self.memory) > self.memory_number*2:
            self._pop()
        else:
            pass

    def get_pipe(self):
        return self.memory
