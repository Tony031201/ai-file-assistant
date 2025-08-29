import os,json,tempfile,shutil,threading
# 路径参数
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
JSON_FILE = os.path.join(DATA_DIR, 'file_index2.json')
DB_FILE = os.path.join(DATA_DIR, 'assistant.db')
HISTORY_RECORD = os.path.join(DATA_DIR, 'history_record.json')


_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
_DEFAULTS = {
    "WATCH_PATH": r"C:\Users\atuon",  # 你的默认目录
    "API_KEY":""
}
_lock = threading.RLock()
_cache = None  # 进程内缓存

def _ensure_parent():
    os.makedirs(os.path.dirname(_CONFIG_PATH), exist_ok=True)

def _load_no_cache() -> dict:
    if os.path.exists(_CONFIG_PATH):
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except Exception:
                data = {}
    else:
        data = {}
    # 合并默认项（未知字段保留）
    cfg = {**_DEFAULTS, **data}
    return cfg

def load() -> dict:
    global _cache
    with _lock:
        if _cache is None:
            _cache = _load_no_cache()
        return _cache.copy()

def save(cfg: dict) -> None:
    """原子写入，防止中途崩溃损坏文件"""
    with _lock:
        _ensure_parent()
        tmp_fd, tmp_path = tempfile.mkstemp(prefix="config_", suffix=".json",
                                            dir=os.path.dirname(_CONFIG_PATH))
        os.close(tmp_fd)
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        shutil.move(tmp_path, _CONFIG_PATH)  # 原子替换
        # 刷新缓存
        global _cache
        _cache = cfg.copy()

# 简便的 getter/setter
def get_watch_path() -> str:
    return load().get("WATCH_PATH", _DEFAULTS["WATCH_PATH"])

def set_watch_path(path: str) -> None:
    cfg = load()
    cfg["WATCH_PATH"] = path
    save(cfg)

def get_api() -> str:
    return load().get("API_KEY", _DEFAULTS["API_KEY"])

def set_api(api:str) -> None:
    cfg = load()
    cfg["API_KEY"] = api
    save(cfg)
