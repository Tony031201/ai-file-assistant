from __future__ import annotations
import json,os,sys,hashlib,traceback
import queue
import threading
from pathlib import Path
from typing import Dict,List,Tuple,Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from claude_sonnet_4 import ClaudClient

# 最大线程为3
DEFAULT_WORKERS = 3
RAW_OUT_DIR = None
ALLOW_EXTS = {".py",".js",".ts",".tsx",".c",".cpp",".h",".hpp",".cs",".java",".go",".rs"}

# 读取api
api_target = Path(__file__).parent.parent.parent/"data"/"config.json"
api_list = []
try:
    print("config 读取路径:",api_target)
    with open(api_target,"r") as f:
        config = json.load(f)
    for i in range(DEFAULT_WORKERS):
        api_list.append(ClaudClient(config[f"SONIC_4_API_KEY_{i+1}"]))
except Exception:
    print("来自项目分析模块: 线程api读取出错")
    sys.exit(1)

# 读取需要遍历的代码文件
target = Path(__file__).resolve().parent.parent/"scan"/"file_path.json"
try:
    with open(target,"r") as f:
        data = json.load(f)
except FileNotFoundError as e:
    print("来自ingest.py:",e)
    sys.exit(1)

root_dir = Path(data["root"]).resolve()
files_list = data["files"]

# 合并根目录和相对目录
def read(root_dir:str,path_dict:dict):
    path = path_dict["path"]
    return root_dir+path

def make_full_path(item: Dict) -> Path:
    """把清单里的相对路径拼成绝对路径，并做一次后缀过滤"""
    p = (root_dir / item["path"]).resolve()
    if p.suffix.lower() not in ALLOW_EXTS:
        return None  # 过滤非代码文件
    return p

def task(client:ClaudClient, abs_path: Path):
    # send_message 接受 str 或 Path 都行，这里传 Path
    return client.send_message(abs_path)

with ThreadPoolExecutor(max_workers=DEFAULT_WORKERS) as pool:
    futures = []
    for idx, item in enumerate(files_list):
        rel = item["path"]
        abs_path = (root_dir / rel).resolve()
        p = make_full_path(item)

        client = api_list[idx%len(api_list)]
        futures.append(pool.submit(task, client, abs_path))

    for f in as_completed(futures):
        path, result = f.result()
        with open(f"store/{path}.txt","w",encoding="utf-8") as e:
            e.write(result)


