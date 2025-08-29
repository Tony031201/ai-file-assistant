模块名称: sql

功能概述:
- 基于 SQLite 的文件索引数据库层。
- 功能覆盖：增删改查、SQL 安全过滤、全量索引重建、实时文件系统追踪。
- 目录结构:
  sql/
  ├─ db_tools.py      # 封装对数据库的 CRUD 操作
  ├─ sql_filter.py    # SQL 过滤器，限制可执行范围
  ├─ sync_rebuild.py  # 扫描磁盘并全量重建数据库表
  └─ tracker.py       # 监听文件系统变动，实时更新数据库

---

### 1) db_tools.py
- **cracker(path: str)**
  解析文件/目录路径，提取 name/ext/size/ctime/mtime 等属性。

- **DBTools 类**
  SQLite 工具类，负责 `files` 表操作。
  - create(path) / create_dir(dir_path): 插入文件或目录记录
  - delete(path): 删除记录
  - update(old_path, new_path): 更新单条记录
  - update_many(old_paths, new_path_dir, old_path_dir): 批量更新路径
  - custom_instruction(sql): 执行自定义 SQL（建议配合 `sql_filter`）
  - list_file_and_dir_paths(path): 列出目录及子目录的所有 path
  - reset_db(): 清空表 `files`

---

### 2) sql_filter.py
- **Output (TypedDict)**: `{sql: str, status: bool}`
- **SQL_Filter(sql: str)**: 检查 SQL 是否安全。

规则：
- 黑名单：`pragma`, `drop`, `delete`, `insert`, `alter`, `create`, `union`, `vacuum` 等。
- 仅允许：
  - `SELECT ... FROM files ...`（不允许多表/逗号）
  - `UPDATE files SET note=... WHERE ...`（只允许修改 `note` 字段，且单列修改）

---

### 3) sync_rebuild.py
- **scan_to_rows(root, should_ignore)**
  递归扫描目录，返回 `files` 表所需的行（文件+目录）。

- **rebuild_files_table(watch_path, should_ignore)**
  全量重扫 → 建立临时表 `files_new` → 插入扫描结果 → 迁移旧表 `note` → 原子换表。
  返回统计字典：`{"scanned": n, "inserted": m}`。

特点：
- 使用事务 `BEGIN IMMEDIATE`，保证操作原子性。
- 支持路径过滤函数 `should_ignore()`。
- 保证原有备注字段不会丢失（迁移 note）。

---

### 4) tracker.py
- **作用**:
  使用 `watchdog` 监听文件系统变化，自动同步数据库。
  支持忽略规则（默认 + `.trackerignore` 文件）。

- **主要函数**:
  - should_ignore(path): 判断路径是否需要忽略
  - initialize(): 初始化数据库（清空后全量扫描 `WATCH_PATH`）
  - start_watching(): 启动文件系统监听
  - stop_watching(): 停止监听

- **FileChangeHandler**（事件回调）
  - on_created(): 文件/目录新增 → 调用 `db_tools.create` 或 `create_dir`
  - on_deleted(): 文件/目录删除 → 调用 `db_tools.delete`
  - on_moved(): 路径移动 → 调用 `db_tools.update` 或 `update_many`
  - on_modified(): 文件修改 → 更新数据库记录

- **忽略机制**:
  - 默认忽略：`.git/`, `__pycache__/`, `node_modules/`, `.log`, `.tmp` 等
  - 支持 `.trackerignore` 文件（类似 .gitignore，支持 `!` 否定规则）

---

依赖:
- 内置库: os, sqlite3, time, pathlib, re, json, sys, fnmatch
- 第三方库: watchdog
- 项目内部:
  - data.meta_data (DB_FILE, HISTORY_RECORD, get_watch_path)
  - core.error_handler.error

---

使用示例:
```python
# 初始化并开始监听
from sql.tracker import initialize, start_watching, stop_watching

initialize()        # 扫描 WATCH_PATH 并建立初始数据库
start_watching()    # 开启监听

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    stop_watching()
