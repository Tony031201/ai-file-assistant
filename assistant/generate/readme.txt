模块名称: generate

功能说明:
- 提供文件生成功能。
- 当前包含文件: create_file.py

主要文件:
1. create_file.py
   - createFile(file_path: str, content: str) -> bool
     功能: 在指定路径创建新文件，并写入给定内容。
     逻辑:
       1. 确保目标目录存在（若不存在则自动创建）。
       2. 若目标文件已存在，返回 False（避免覆盖）。
       3. 若文件不存在，则写入 content，返回 True。
       4. 发生异常时，调用 core.error_handler.error 输出错误信息，并返回 False。

依赖:
- 内置库: os
- 项目内部: core.error_handler.error

使用方法:
```python
from generate.create_file import createFile

file_path = "output/demo.txt"
content = "Hello, world!"

if createFile(file_path, content):
    print("文件创建成功")
else:
    print("文件已存在或创建失败")
