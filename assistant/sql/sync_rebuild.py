import os, time, sqlite3
from pathlib import Path
from typing import Tuple, List, Dict, Callable
from sql.db_tools import DBTools  # 你已有
from core.error_handler import error

def _file_meta(p: Path) -> Tuple[str,str,str,str,int,int,int,int,int,str]:
    st = p.stat()
    is_dir = p.is_dir()
    return (
        str(p.resolve()),       # path
        p.name,                 # name
        p.name.lower(),         # case_key
        "" if is_dir else p.suffix,   # ext
        0 if is_dir else int(st.st_size),    # size
        int(st.st_mtime),       # mtime
        int(st.st_ctime),       # ctime
        1 if is_dir else 0,     # deleted: 1=目录, 0=文件（与你 schema 注释一致）
        int(time.time()),       # updated_at
        "",                     # note（先空，后面迁移）
    )

def scan_to_rows(root: str, should_ignore: Callable[[str], bool]) -> List[Tuple]:
    rows: List[Tuple] = []
    rootp = Path(root).resolve()
    # 根目录也可入库（目录项）
    if not should_ignore(str(rootp)):
        rows.append(_file_meta(rootp))
    for cur, dnames, fnames in os.walk(root):
        # 过滤将要深入的目录，避免 node_modules/venv 巨树
        dnames[:] = [d for d in dnames if not should_ignore(os.path.join(cur, d))]
        # 目录项
        for d in dnames:
            dp = Path(cur, d)
            if should_ignore(str(dp)):
                continue
            try:
                rows.append(_file_meta(dp))
            except Exception as e:
                error("sync_rebuild.py", "scan_dir", e)
        # 文件项
        for f in fnames:
            fp = Path(cur, f)
            if should_ignore(str(fp)):
                continue
            try:
                rows.append(_file_meta(fp))
            except Exception as e:
                error("sync_rebuild.py", "scan_file", e)
    return rows

# -------- 2) 重建：files_new → 迁移 note → 原子换表 --------
DDL_FILES = """
CREATE TABLE IF NOT EXISTS {tbl} (
  id         INTEGER PRIMARY KEY,
  path       TEXT UNIQUE NOT NULL,
  name       TEXT NOT NULL,
  case_key   TEXT NOT NULL,
  ext        TEXT,
  size       INTEGER,
  mtime      INTEGER,
  ctime      INTEGER,
  deleted    INTEGER DEFAULT 0,
  updated_at INTEGER NOT NULL,
  note       TEXT
);
"""

INDEXES = [
    # ("idx_files_path", "CREATE UNIQUE INDEX IF NOT EXISTS idx_files_path ON {tbl}(path)"),
]

def rebuild_files_table(watch_path: str, should_ignore: Callable[[str], bool]) -> Dict[str, int]:
    """
    全量重扫 → 建 files_new → 批插 → 迁移 note → 原子换表。
    返回统计：{'scanned': n, 'inserted': m}
    """
    rows = scan_to_rows(watch_path, should_ignore)
    stats = {"scanned": len(rows), "inserted": 0}

    db = DBTools()
    conn: sqlite3.Connection = db.conn
    cur: sqlite3.Cursor = db.cur

    try:
        cur.execute("BEGIN IMMEDIATE")
        cur.execute("PRAGMA foreign_keys = OFF")

        # 备份旧表（可选）
        cur.execute("DROP TABLE IF EXISTS files_backup")
        cur.execute("CREATE TABLE files_backup AS SELECT * FROM files")

        # 新表
        cur.execute("DROP TABLE IF EXISTS files_new")
        cur.execute(DDL_FILES.format(tbl="files_new"))
        for name, sql_tpl in INDEXES:
            cur.execute(sql_tpl.format(tbl="files_new"))

        # 批量插入扫描结果
        cur.executemany(
            """
            INSERT INTO files_new
            (path,name,case_key,ext,size,mtime,ctime,deleted,updated_at,note)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            rows
        )
        stats["inserted"] = cur.rowcount if cur.rowcount is not None else 0

        # 迁移旧表 note（以 path 对齐）
        cur.execute(
            """
            UPDATE files_new
            SET note = COALESCE((
              SELECT note FROM files old WHERE old.path = files_new.path
            ), files_new.note)
            WHERE EXISTS (SELECT 1 FROM files old WHERE old.path = files_new.path)
            """
        )

        # 原子换表
        cur.execute("ALTER TABLE files RENAME TO files_old")
        cur.execute("ALTER TABLE files_new RENAME TO files")

        # 如需将索引重建到新表名（若你在 INDEXES 用了固定名，这里再建一次）
        for name, sql_tpl in INDEXES:
            cur.execute(sql_tpl.format(tbl="files"))

        # 删除旧表
        cur.execute("DROP TABLE IF EXISTS files_old")

        cur.execute("PRAGMA foreign_keys = ON")
        conn.commit()
        print(f"[rebuild] scanned={stats['scanned']} inserted≈{stats['inserted']}")
        return stats

    except Exception as e:
        try: conn.rollback()
        except: pass
        error("sync_rebuild.py", "rebuild_files_table", e)
        # 回滚后尽量恢复旧表（若需要可从 files_backup 还原）
        return stats
    finally:
        db.close()