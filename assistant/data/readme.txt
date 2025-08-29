模块名称: data

功能概述:
- 存放程序运行所需的数据与配置，包括数据库、样式、提示词与配置读写逻辑。
- 提供线程安全、带缓存与“原子写入”的配置管理（见 meta_data.py）。

目录结构（示例）:
data/
├─ assistant.db            # SQLite 数据库（可随仓库上传，用于功能演示/默认数据）
├─ config.example.json     # 配置模板（示例：API_KEY、WATCH_PATH）
├─ config.json             # 实际运行配置（由程序生成/修改）
├─ prompt.txt              # 系统提示词（system prompt）
├─ style.qss               # 应用的 QSS 样式
└─ meta_data.py            # 配置与路径管理工具

文件说明:
1) assistant.db
   - SQLite 数据库文件。计划上传到仓库，方便开箱即用。
   - 如果涉及敏感/用户数据，生产环境建议使用迁移脚本初始化而非直接上传。

2) config.example.json
   - 示例配置文件（建议提交到仓库）。
   - 用途：提示使用者把它复制为 config.json 并填写真实值。
   - 典型内容:
     {
       "WATCH_PATH": "C:\\Users\\yourname",
       "API_KEY": "your-api-key-here"
     }

3) config.json
   - 实际生效的配置文件（程序运行时读写）。
   - 建议加入 .gitignore，避免把密钥/本地路径提交到仓库。

4) prompt.txt
   - 存放系统提示词（system prompt）。被 core/test_claud.py 读取，用于设置 Claude 的 system 字段。

5) style.qss
   - 存放 UI 的样式表（Qt/QSS）。

6) meta_data.py
   - 负责路径与配置管理的核心工具模块：
     - 常量与路径:
       BASE_DIR         # 项目根目录
       DATA_DIR         # data 目录
       DB_FILE          # assistant.db
       HISTORY_RECORD   # history_record.json（如需使用）
       _CONFIG_PATH     # data/config.json

     - 默认配置:
       _DEFAULTS = {
         "WATCH_PATH": "C:\\Users\\atuon",
         "API_KEY": ""
       }

     - 并发控制:
       _lock = threading.RLock()   # 可重入锁，避免重入/嵌套死锁
       _cache = None               # 进程内缓存，减少 IO

     - 读取流程（带缓存）:
       load() -> dict
         * 首次调用使用 _load_no_cache() 读 config.json 并与 _DEFAULTS 合并
         * 返回字典的副本（.copy()），避免外部修改污染缓存
       _load_no_cache() -> dict
         * 若 config.json 存在则加载；否则使用空字典
         * 与 _DEFAULTS 合并，未提供的键使用默认值

     - 原子写入:
       save(cfg: dict) -> None
         * 先写入临时文件，再用 shutil.move 原子替换为 config.json
         * 写入成功后刷新内存缓存 _cache = cfg.copy()

     - 易用 API:
       get_watch_path() -> str
       set_watch_path(path: str) -> None
       get_api() -> str
       set_api(api: str) -> None

用法示例:
1) 初始化配置（首次运行/修改默认值）
```python
from data.meta_data import set_watch_path, set_api, get_watch_path, get_api

set_watch_path(r"D:\Projects\my_watch_dir")
set_api("sk-xxxx-your-key")
print(get_watch_path())  # D:\Projects\my_watch_dir
print(get_api())         # sk-xxxx-your-key
