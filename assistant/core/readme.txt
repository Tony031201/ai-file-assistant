模块名称: core

功能说明:
- 提供项目的核心基础功能，包括：
  1. AI 输出解析
  2. 错误处理
  3. 对话记忆管理
  4. Claude API 测试客户端

主要文件:
1. ai_parse.py
   - Response (TypedDict)
     定义标准响应格式，包含 answer、instruction、file_path、file_content、sql。
   - parse_response(raw_text: str) -> dict
     解析模型输出文本，提取五个固定段落（回答、指令、文件路径、文件内容、SQL）。
     * 支持 ```sql ...``` 代码块 或行内 SQL
     * 缺少必需段落会抛出 ValueError
   - merge_response(response: Response) -> str
     将解析结果重新拼接为统一字符串。

2. error_handler.py
   - error(f_name: str, f: str, e: Exception) -> None
     简单的错误日志输出函数，打印格式为：
     ```
     {f_name}文件,函数:{f}: {e}
     ```
     用于捕获并打印错误。

3. memory_pipe.py
   - Message (TypedDict)
     定义对话消息结构，包含 role 与 content。
   - Memory_Pipe(memory_number: int)
     对话记忆管道：
       * __init__(self, memory_number): 初始化容量
       * _push(message): 添加消息
       * _pop(): 移除最早的消息
       * process(message): 添加消息并保持总条数 <= memory_number * 2
       * get_pipe(): 返回当前记忆列表

4. test_claud.py
   - ClaudClient 类
     * __init__(): 初始化 Claude 客户端，读取 API key（data.meta_data.get_api）和系统提示词（data/prompt.txt）
     * send_message(messages: str) -> str: 使用 Claude API 发送消息，附加系统提示词，返回生成结果

依赖:
- 内置库: re, typing, sys
- 第三方库: anthropic
- 项目内部: data.meta_data.get_api

使用方法:
```python
# 示例：解析 AI 输出
from core.ai_parse import parse_response
raw_text = "回答: hi\n指令: test\n参数块:\n文件路径: demo.py\n生成文件内容: print('ok')\n可执行SQL:\n```sql\nSELECT 1;\n```"
print(parse_response(raw_text))

# 示例：使用 Memory_Pipe 管理对话
from core.memory import Memory_Pipe
pipe = Memory_Pipe(memory_number=2)
pipe.process({"role": "user", "content": "你好"})
pipe.process({"role": "assistant", "content": "你好呀"})
print(pipe.get_pipe())

# 示例：Claude API 测试客户端
from core.test_claud import ClaudClient
client = ClaudClient()
print(client.send_message("帮我写一个Hello World程序"))
