模块名称: cmd

功能概述:
- 基于安全过滤的系统命令执行模块。
- 功能覆盖：命令安全过滤、系统命令执行、命令历史记录、批量命令处理。
- 目录结构:
  cmd/
  ├─ cmd_filter.py    # 命令安全过滤器，限制可执行命令范围
  ├─ cmd_tools.py     # 封装系统命令执行的工具类
  ├─ cmd_history.py   # 命令执行历史记录管理
  └─ cmd_executor.py  # 命令执行器，整合过滤、执行和历史功能

---

### 1) cmd_filter.py
- **CMD_Filter(cmd: str)**
  检查命令是否安全，防止执行危险的系统命令。

规则：
- 黑名单：`shutdown`, `rm -rf`, `del /f`, `format`, `reboot`, `passwd` 等危险命令。
- 白名单：仅允许：
  - 文件查看：`ls`, `dir`, `cat`, `type`, `head`, `tail` 等
  - 系统信息：`ps`, `top`, `systeminfo`, `uname`, `whoami` 等
  - 网络查看：`ping`, `tracert`, `nslookup`, `netstat` 等
  - 安全的文件操作：`mkdir`, `touch`, `cp`, `copy`, `mv` 等
- 高风险关键词检查：防止路径遍历、命令注入等攻击
- 参数安全性检查：即使是安全命令也检查参数是否包含危险内容

- **Output (TypedDict)**: `{cmd: str, status: bool}`

---

### 2) cmd_tools.py
- **CommandResult**: 命令执行结果数据类
  包含命令、成功状态、输出、错误信息、返回码、执行时间等。

- **CMDTools 类**
  系统命令执行工具类，负责安全地执行系统命令。
  - execute_command(command, cwd): 执行单个命令
  - execute_safe_command(command, cwd): 执行安全命令并返回简化结果
  - get_system_info(): 获取系统信息
  - change_directory(path): 更改当前工作目录
  - list_directory(path): 列出目录内容
  - is_command_safe(command): 检查命令是否安全

特性：
- 跨平台支持（Windows/Linux/macOS）
- 命令执行超时控制（默认30秒）
- 输出长度限制（防止内存溢出）
- 编码处理（Windows GBK，Unix UTF-8）
- 工作目录管理

---

### 3) cmd_history.py
- **CommandHistoryEntry**: 命令历史记录条目数据类
  包含ID、命令、时间戳、执行结果、输出、错误信息等。

- **CommandHistory 类**
  命令执行历史记录管理类。
  - add_command(): 添加命令执行记录
  - get_recent_commands(limit): 获取最近的命令记录
  - search_commands(keyword, limit): 搜索包含关键词的命令
  - get_failed_commands(limit): 获取失败的命令记录
  - get_command_by_id(id): 根据ID获取特定命令记录
  - get_statistics(): 获取命令执行统计信息
  - clear_history(): 清空命令历史
  - export_history(path): 导出历史到文件

特性：
- JSON格式持久化存储（cmd_history.json）
- 历史记录数量限制（默认1000条）
- 输出长度限制（防止存储过大）
- 统计分析功能（成功率、常用命令等）
- 搜索和过滤功能

---

### 4) cmd_executor.py
- **CommandExecutor 类**
  命令执行器，cmd模块的主要对外接口，整合所有功能。
  - execute(command, cwd): 执行命令主接口
  - batch_execute(commands): 批量执行命令
  - get_command_help(command): 获取命令帮助信息
  - test_command_safety(command): 测试命令安全性（不执行）
  - get_system_info(): 获取系统信息
  - change_directory(path): 更改工作目录
  - list_directory(path): 列出目录内容
  - get_history(limit): 获取命令历史
  - search_history(keyword): 搜索命令历史
  - get_statistics(): 获取执行统计

特性：
- 命令安全过滤集成
- 自动历史记录（可选）
- 批量命令处理
- 错误处理和异常捕获
- 统一的结果格式
- 全局执行器实例（executor）

---

安全特性:
- 多层安全防护：黑名单 + 白名单 + 参数检查
- 命令注入防护：过滤危险字符和路径遍历
- 权限限制：禁止sudo和管理员命令
- 超时控制：防止长时间运行的命令
- 输出限制：防止大量输出造成内存问题
- 历史记录：所有命令执行都有日志记录

依赖:
- 内置库: subprocess, os, sys, time, json, re, threading
- 项目内部:
  - core.error_handler.error
  - data.meta_data (DATA_DIR, get_watch_path)

---

使用示例:
```python
# 导入命令执行器
from cmd.cmd_executor import executor

# 执行单个命令
result = executor.execute("ls -la")
if result["success"]:
    print("输出:", result["output"])
else:
    print("错误:", result["error"])

# 批量执行命令
commands = ["pwd", "ls", "whoami"]
batch_result = executor.batch_execute(commands)

# 测试命令安全性
safety_test = executor.test_command_safety("rm -rf /")
print("是否安全:", safety_test["is_safe"])

# 获取命令历史
history = executor.get_history(10)
print("最近10条命令:", history["commands"])

# 搜索历史
search_result = executor.search_history("ls")
print("包含ls的命令:", search_result["commands"])

# 获取统计信息
stats = executor.get_statistics()
print("成功率:", stats["success_rate"])
```

---

与sql模块的区别:
- sql模块专注于数据库操作和文件监控
- cmd模块专注于系统命令执行和安全控制
- sql模块操作结构化数据，cmd模块处理系统级操作
- 两个模块互补，sql负责文件索引，cmd负责系统交互

注意事项:
- 命令执行需要通过安全过滤器，危险命令会被拦截
- 所有命令执行都会记录历史（可关闭）
- 跨平台兼容性：Windows和Unix系统的命令差异会自动处理
- 超时设置：长时间运行的命令会被终止
- 工作目录：支持指定命令执行的工作目录
- 编码问题：自动处理中文和特殊字符编码