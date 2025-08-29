from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time,os,json,sys
from sql.db_tools import DBTools
from data.meta_data import HISTORY_RECORD,DB_FILE,get_watch_path
from core.error_handler import error
import fnmatch
from pathlib import Path

f_name = "tracker.py"
INDEX_FILE = "../data/file_index2.json"

# 项目根目录的ignore文件(放在 WATCH PATH 的根部)
TRACKERIGNORE = os.path.join(get_watch_path(), ".trackerignore")

# 需要忽略的类型
# 默认忽略目录/文件/后缀（可按需增删）
DEFAULT_IGNORE_DIRS = {
    ".git", ".hg", ".svn", ".idea", ".vscode",
    "__pycache__", ".mypy_cache", ".pytest_cache",
    "dist", "build", ".cache", ".local",
    "node_modules", ".pnpm-store", ".yarn", ".parcel-cache",
    "venv", ".venv", "env",
    "Lib", "site-packages",  # Windows venv 常见
}
DEFAULT_IGNORE_FILE_SUFFIX = {
    ".pyc", ".pyo", ".pyd", ".so", ".dll",
    ".tmp", ".temp", ".swp", ".swx", ".log",
    ".crdownload", ".part", ".download",
}
DEFAULT_IGNORE_FILE_NAMES = {"desktop.ini", "thumbs.db", ".ds_Store"}


def _norm(p:str) -> str:
    # 统一大小写与分隔符，方便匹配。把任意输入路径 规范化 成一个稳定的字符串
    return Path(p).resolve().as_posix().lower()

def _rel(p:str) -> str:
    # 转相对路径，便于.trackerignore 用相对规则
    try:
        return Path(p).resolve().relative_to(Path(get_watch_path()).resolve()).as_posix().lower()
    except ValueError:
        # 如果p不处于监听目录下，那么就转移到 _norm(p)（绝对路径）
        return _norm(p)

def _load_trackerignore() -> tuple[list[str], list[str]]:
    # 负责读取并解析 .trackerignore 文件里的规则
    pats, neg = [], []      # pats: 普通忽略规则, neg: 否定规则
    if os.path.exists(TRACKERIGNORE):
        with open(TRACKERIGNORE, "r",encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith("#"): continue
                if s.startswith("!"):
                    neg.append(s[1:].strip())
                else:
                    pats.append(s)
    return pats, neg

# 程序启动前，先读一遍
IGNORE_GLOBS, IGNORE_NEG_GLOBS = _load_trackerignore()

def should_ignore(p:str) -> bool:
    p_abs = _norm(p)
    p_rel= _rel(p)
    base = os.path.basename(p_abs)

    # 开始排除
    # 1) 排除数据库本体以及衍生
    dbn = _norm(DB_FILE)
    if p_abs == dbn:
        return True
    if p_abs.startswith(dbn):
        tail = p_abs[len(dbn):]
        if any(s in tail for s in (".wal", "-wal", ".journal", "-journal")):
            return True

    # 2) 默认文件名/后缀
    if base in DEFAULT_IGNORE_FILE_SUFFIX:
        return True
    if any(base.endswith(suf) for suf in DEFAULT_IGNORE_FILE_SUFFIX):
        return True

    # 3) 默认目录命中(路径段包含任一忽略目录)
    parts = Path(p_abs).parts
    if any(seg.lower in DEFAULT_IGNORE_DIRS for seg in parts):
        # 允许被 .trackerignore 的否定规则覆盖，继续看第4步
        pass

    # 4) .trackerignore（glob），相对与绝对都试
    def _glob_hit(p: str, patterns: list[str]) -> bool:
        return any(fnmatch.fnmatch(p, pat.lower()) for pat in patterns)

    if _glob_hit(p_rel, IGNORE_GLOBS) or _glob_hit(p_abs, IGNORE_GLOBS):
        # 若被否定规则命中，则不忽略
        if _glob_hit(p_rel, IGNORE_NEG_GLOBS) or _glob_hit(p_abs, IGNORE_NEG_GLOBS):
            return False
        return True

    # 5) 若路径段包含默认忽略目录，且没有被否定覆盖 → 忽略
    if any(seg.lower() in DEFAULT_IGNORE_DIRS for seg in parts):
        if _glob_hit(p_rel, IGNORE_NEG_GLOBS) or _glob_hit(p_abs, IGNORE_NEG_GLOBS):
            return False
        return True

    return False


# 修改json目录 #
def load_index():
    if not os.path.exists(INDEX_FILE):
        return []
    with open(INDEX_FILE,'r',encoding='utf-8') as f:
        return json.load(f)

# 通用, 加载json文件
def load_json(json_path:str):
    if not os.path.exists(json_path):
        print(f"找不到{json_path}文件")
        return []
    with open(json_path,'r',encoding='utf-8') as f:
        return json.load(f)

def save_index(index):
    with open(INDEX_FILE,'w',encoding='utf-8') as f:
        json.dump(index,f,indent=2,ensure_ascii=False)

def add_to_index(filepath, is_directory:bool):
    filepath = os.path.normpath(filepath)
    dbtools = DBTools()
    print("在里:",filepath)

    try:
        if not is_directory:
            if dbtools.create(filepath):
                print(f"new file added: {filepath}")
        else:
            if dbtools.create_dir(filepath):
                print(f"new dir added: {filepath}")
    except Exception as e:
        error(f_name,"add_to_index",e)
    finally:
        dbtools.close()

def remove_from_index(filepath, is_directory = False):
    filepath = os.path.normpath(filepath)
    dbtools = DBTools()

    try:
        if dbtools.delete(filepath):
            print(f"File removed: {filepath}")
    except Exception as e:
        error(f_name,"remove_from_index",e)
    finally:
        dbtools.close()


def update_index(old_path,new_path,is_directory = False):
    history = load_json(HISTORY_RECORD)

    # 统一路径分隔符
    old_path = os.path.normpath(old_path)
    new_path = os.path.normpath(new_path)

    # 前缀检查
    if old_path in history:
        return

    dbtools = DBTools()
    try:
        # 非目录项的修改
        if not is_directory :
            # 单个更新
            print("非目录项的修改")
            dbtools.update(old_path,new_path)
        else:
            # 目录项的修改
            print("目录项的修改")
            # 递归查找需要改变的全部文件
            update_list = dbtools.list_file_and_dir_paths(old_path)
            print(f"需要修改的文件数量:{len(update_list)}")
            # 更新前缀记录文件
            with open(HISTORY_RECORD,'w',encoding='utf-8') as f:
                json.dump(update_list,f,indent=2,ensure_ascii=False)
            # 批量更新
            dbtools.update_many(update_list,new_path+os.sep,old_path+os.sep)
    except Exception as ex:
        error(f_name,"update_index",ex)
    finally:
        dbtools.close()

def modify_index(path:str):
    path = os.path.normpath(path)
    dbtools = DBTools()
    try:
        dbtools.update(path,path)
    except Exception as e:
        error(f_name,"modify_index",e)
    finally:
        dbtools.close()

def clear_json(json_path:str) -> bool:
    if not os.path.exists(json_path):
        print(f"错误来自 tracker clear_json函数: 文件{json_path}不存在")
        return False
    else:
        with open(json_path,'w',encoding='utf-8') as f:
            json.dump([],f,indent=2,ensure_ascii=False)
        return True

# 事件监听器 #
class FileChangeHandler(FileSystemEventHandler):
    def on_created(self, event):
        src = os.path.normpath(event.src_path)
        if should_ignore(src):
            return
        add_to_index(src, is_directory=event.is_directory)
        clear_json(HISTORY_RECORD)

    def on_deleted(self, event):
        src = os.path.normpath(event.src_path)
        if should_ignore(src):
            return
        remove_from_index(src,event.is_directory)
        clear_json(HISTORY_RECORD)


    def on_moved(self, event):
        src = os.path.normpath(event.src_path)
        dst = os.path.normpath(event.dest_path)

        # 两端都应忽略
        if should_ignore(src) and should_ignore(dst):
            return

        # 一端在工作集、一端被忽略：等价于 “增 或 删”
        if should_ignore(src) and not should_ignore(dst):
            add_to_index(dst, is_directory=event.is_directory)
            clear_json(HISTORY_RECORD)
            return

        if not should_ignore(src) and should_ignore(dst):
            remove_from_index(src, event.is_directory)
            clear_json(HISTORY_RECORD)
            return

        update_index(src, dst, is_directory = event.is_directory)
        # print(f"ON move 触发， SRC:{event.src_path}, DEST:{event.dest_path}, IS DIR:{event.is_directory}")



# 初始化 #
def initialize(reset:bool = False):
    print("初始化中...")
    dbtools = DBTools()
    dbtools.reset_db()      # 清空数据库
    for root, dirs, files in os.walk(get_watch_path()):
        # 原地过滤目录
        dirs[:] = [d for d in dirs if not should_ignore(os.path.join(root, d))]

        # 目录入库
        for d in dirs:
            dp = os.path.normpath(os.path.join(root, d))
            if not should_ignore(dp):
                try:
                    dbtools.create_dir(dp)
                except Exception as e:
                    error("sql/tracker.py", "initialize.create_dir", e)

        # 文件入库
        for file in files:
            filepath = os.path.normpath(os.path.join(root,file))
            if should_ignore(filepath):
                continue
            try:
                dbtools.create(filepath)
            except Exception as e:
                error("sql/tracker.py", "initialize.create_file", e)
    dbtools.close()
    print("初始化完成")


observer = None     # 将监听器作为全局变量

# 启动器 #
def start_watching():
    global observer
    if not os.path.exists(HISTORY_RECORD):
        print("From tracker: history_record.json 文件缺失")
        sys.exit(1)
    print("监听开始")
    event_handler = FileChangeHandler()
    observer = Observer()
    observer.schedule(event_handler, get_watch_path(), recursive=True)
    observer.start()


def stop_watching():
    global observer
    if observer:
        try:
            observer.stop()
            observer.join()
            print("监听已停止")
        except Exception as e:
            print("停止监控时出错:", e)
        finally:
            observer = None

if __name__ == "__main__":
    # 脚本模式
    initialize()
    start_watching()
    try:
        while observer and observer.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        stop_watching()
