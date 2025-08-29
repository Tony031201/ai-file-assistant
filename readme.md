项目名称: AI 文件助手 (File Assistant)

简介
本项目是一个本地运行的 AI 文件助手，具备以下功能：
- 文件/目录的监听与索引（实时追踪文件变化）
- 与 Claude API 对接的智能分析 (analyse 模块)
- 文件生成与管理 (generate 模块)
- SQL 数据库工具与查询过滤 (sql 模块)
- 自动化数据可视化 (visualization 模块)
- 内部工具: 配置管理、错误处理、对话记忆 (core, data 模块)

主程序入口为 main.py。

数据库初始化
------------------------------------------------------------
本项目使用 SQLite 数据库 assistant.db 储存文件索引。

首次运行前，请在 data/ 文件夹下创建一个空的数据库文件：

Linux / macOS:
    cd data
    sqlite3 assistant.db ""

Windows (PowerShell):
    cd data
    echo. > assistant.db

或者手动在 data/ 下新建一个名为 assistant.db 的空文件。

随后，运行主程序:
    python assistant/main.py

------------------------------------------------------------
运行环境
------------------------------------------------------------
- Python 版本: 3.10.10
- 系统: Windows / Linux / macOS（部分功能如 os.startfile 仅限 Windows）

------------------------------------------------------------
准备工作
------------------------------------------------------------
1. 安装依赖
   在项目根目录执行:
    pip install -r requirements.txt


2. 配置 API Key 与监听目录
- 打开 data 文件夹
- 将 `config.example.json` 重命名为 `config.json`
- 填写你的 API Key (Anthropic Claude) 和监听路径 (watch_path)，例如：
  ```json
  {
    "WATCH_PATH": "C:\\Users\\atuon",
    "API_KEY": "sk-xxxxxx"
  }
  ```

3. 数据库初始化
- 首次启动会在 data/ 下生成 assistant.db 并自动维护文件索引

------------------------------------------------------------
使用方式
------------------------------------------------------------
启动主程序:
    python main.py


程序功能:
- 自动监听 WATCH_PATH 目录
- 新建/删除/移动文件会实时更新数据库
- 可调用 analyse 模块对文件内容进行 AI 分析
- 可调用 generate 模块生成新文件
- 可通过 SQL 模块查询或更新数据库记录
- 可通过 visualization 模块对数据文件生成自动化可视化图表

------------------------------------------------------------
目录结构
------------------------------------------------------------
- main.py                # 主入口
- requirements.txt       # 依赖文件
- .gitignore             # 忽略文件（默认包含 venv/ config.json 等）

modules/
├─ analyse/              # AI 分析功能
│   ├─ analyse.py
│   └─ analyse_claud.py
│   └─ readme.txt
├─ core/                 # 基础工具
│   ├─ ai_parse.py       # AI 输出解析
│   ├─ error_handler.py  # 错误日志
│   ├─ memory_pipe.py    # 对话记忆
│   ├─ test_claud.py     # 测试 Claude 接口
│   └─ readme.txt
├─ data/                 # 数据与配置
│   ├─ assistant.db      # SQLite 数据库
│   ├─ config.json       # 配置文件 (需手动准备)
│   ├─ config.example.json
│   ├─ prompt.txt        # AI 提示词
│   ├─ style.qss         # 界面样式
│   ├─ meta_data.py      # 配置管理
│   └─ readme.txt
├─ generate/             # 文件生成
│   ├─ create_file.py
│   └─ readme.txt
├─ sql/                  # SQL 数据库管理与监听
│   ├─ db_tools.py
│   ├─ sql_filter.py
│   ├─ sync_rebuild.py
│   ├─ tracker.py
│   └─ readme.txt
└─ visualization/        # 数据可视化
    ├─ determine.py
    ├─ gen_candidates.py
    ├─ scorer.py
    ├─ renderer.py
    ├─ pipeline.py
    ├─ interface.py
    └─ readme.txt

------------------------------------------------------------
注意事项
------------------------------------------------------------
- 首次运行前必须配置好 data/config.json，否则程序无法启动。
- visualization 模块默认使用 Windows 字体路径；若在 Linux/macOS 下运行，请修改 interface.py 的字体配置。
- os.startfile 打开图片仅适用于 Windows；其他系统请改用 open/xdg-open。
- SQLite 数据库 (assistant.db) 采用 WAL 模式，推荐不要直接手动修改。
- 若遇到中文乱码，检查字体配置或安装相应中文字体。

------------------------------------------------------------
作者: Tony,Yule
------------------------------------------------------------
- Python 版本: 3.10.10
- 模块化设计，方便扩展/维护


