模块名称: analyse

功能说明:
- 提供文件内容的自动化分析能力。
- 核心流程：
  1. 从本地读取指定文件的内容
  2. 调用 Claude API（通过 ClaudClient 封装）进行分析
  3. 返回模型生成的分析结果

主要文件:
1. analyse.py
   - _read_file(file_path: str) -> str
     读取本地文件内容，如果文件不存在则调用 error_handler 记录错误。
   - analyze(purpose: str, file_path: str) -> str
     分析指定文件：
       * 读取文件内容
       * 调用 ClaudClient 发送“分析目的 + 文件内容”
       * 返回 AI 分析结果

2. analyse_claud.py
   - ClaudClient 类
     * __init__(): 初始化 Claude API 客户端，设置 API key、模型和 token 上限
     * send_message(messages: str) -> str: 向 Claude API 发送消息并返回生成结果文本

依赖:
- 内置库: os, json
- 第三方库: anthropic
- 项目内部: core.error_handler, data.meta_data.get_api

使用方法:
```python
from analyse.analyse import analyze

purpose = "检查代码可能的错误"
file_path = "example.py"
result = analyze(purpose, file_path)
print(result)
