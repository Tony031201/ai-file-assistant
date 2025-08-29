import sqlite3,os,time
import sys
from core.error_handler import error
from data.meta_data import DB_FILE,JSON_FILE,HISTORY_RECORD,get_watch_path
from pathlib import Path

# 数据表结构（简要）
# ----------------
# 表：files
# - id         INTEGER PRIMARY KEY
# - path       TEXT UNIQUE NOT NULL     # 绝对路径（已规范化）
# - name       TEXT NOT NULL            # 文件名
# - case_key   TEXT NOT NULL            # 文件名小写，用于不区分大小写检索
# - ext        TEXT                     # 扩展名（含点，如 .pdf）
# - size       INTEGER                  # 文件大小（字节）
# - mtime      INTEGER                  # 修改时间戳（秒）
# - ctime      INTEGER                  # 创建时间戳（秒）
# - deleted    INTEGER DEFAULT 0        # 是否为目录项，0为文件，1为目录
# - updated_at INTEGER NOT NULL         # 记录最近变更时间戳（秒）
# - note       TEXT                     # 备注/标签（便于检索）
#
# 关键约定
# --------
# 1) 路径规范化：所有对外暴露的接口都会在入库前使用 os.path.normpath。
# 2) 软删除：delete() 不物理删除，置 deleted=1；查询时请加过滤（deleted=0）。
# 3) UPSERT：create() / update() 在路径冲突时默认更新（ON CONFLICT(path) DO UPDATE）。
# 4) 时间字段：updated_at 统一使用 int(time.time())。
# 5) 文件元数据来源：
#    - 严格模式：通过 cracker(path) 从真实文件提取（os.stat），不存在则抛 FileNotFoundError。
#    - 若仅需修改库中路径而不校验落盘文件，另行实现“path-only”更新（示例见注释）。
#
# 快速上手
# --------
# from db_tools import DBTools
# db = DBTools(DB_FILE)
#
# # 新增或更新（UPSERT）
# db.create(r"C:\Users\me\Docs\report.pdf", note="季度报告")
#
# # 逻辑删除
# db.delete(r"C:\Users\me\Docs\report.pdf")
#
# # 移动/重命名：用旧路径定位，用新路径重算全部元数据并更新
# db.update(old_path=r"C:\Users\me\Docs\old.txt", new_path=r"C:\Users\me\Docs\new.txt")
#
# # 自定义 SQL（开发期）：仅调试用，上线请加白名单过滤
# rows = db.custom_instruction("SELECT name, note FROM files WHERE deleted=0 LIMIT 5")
# print(rows)
#
#
# # 关闭连接
# db.close()
#
#
# 常见坑 & 提示
# -------------
# - 参数化查询：单参数需要元组写法 (value,)；避免 f-string 拼接引发注入或转义问题。
# - fetchall 时机：仅对 SELECT 使用；UPDATE/INSERT/DELETE 取 rowcount 并 commit。
# - 文件不存在：严格模式下 create()/update() 依赖 os.stat，若文件已被移动或删除会报错。
# - LIKE 与大小写：对 name 的不区分大小写检索请使用 case_key（已建 idx_case_key）。
# - 备注检索：note 字段已建 idx_note，适合 “按备注模糊搜索”。

f_name = "db_tools.py"

def cracker(path:str):
    path = os.path.normpath(path)
    if not os.path.exists(path):  # JSON里可能有已不存在的路径
        raise FileNotFoundError(f"from cracker: 路径不存在 -> {path}")
    st = os.stat(path)
    dirpath, name = os.path.split(path)
    ext = os.path.splitext(name)[1].lower()
    case_key = name.lower()
    return path, name, case_key, ext, st.st_size, int(st.st_mtime), int(st.st_ctime)


class DBTools:
    """工具类"""
    def __init__(self):
        # 连接本地数据库
        self.conn = sqlite3.connect(DB_FILE)
        self.cur = self.conn.cursor()
        self.cur.execute("PRAGMA journal_mode=WAL")
        self.cur.execute("PRAGMA synchronous=NORMAL")

        self._ensure_schema()

    def _ensure_schema(self):
        self.cur.executescript("""
        PRAGMA foreign_keys=ON;

        CREATE TABLE IF NOT EXISTS files (
          id         INTEGER PRIMARY KEY AUTOINCREMENT,
          path       TEXT UNIQUE NOT NULL,        -- 绝对路径（已规范化）
          name       TEXT NOT NULL,               -- 文件名
          case_key   TEXT NOT NULL,               -- 文件名小写（或规则化）用于不区分大小写检索
          ext        TEXT,                        -- 扩展名（含点，如 .pdf）
          size       INTEGER,                     -- 字节
          mtime      INTEGER,                     -- 修改时间戳（秒）
          ctime      INTEGER,                     -- 创建时间戳（秒）
          deleted    INTEGER DEFAULT 0,           -- 软删除标记：0=在库，1=已删除（如你要表示“是否目录”，建议改列名为 is_dir）
          is_dir     INTEGER DEFAULT 0,           -- 是否为目录：0=文件，1=目录（如不需要可删）
          updated_at INTEGER NOT NULL DEFAULT (strftime('%s','now')), -- 最近变更时间戳（秒）
          note       TEXT                         -- 备注/标签
        );

        CREATE INDEX IF NOT EXISTS idx_files_case_key ON files(case_key);
        CREATE INDEX IF NOT EXISTS idx_files_ext      ON files(ext);
        CREATE INDEX IF NOT EXISTS idx_files_mtime    ON files(mtime);
        CREATE INDEX IF NOT EXISTS idx_files_deleted  ON files(deleted);

        -- 自动维护 updated_at
        CREATE TRIGGER IF NOT EXISTS trg_files_updated_at
        AFTER UPDATE ON files
        FOR EACH ROW
        WHEN NEW.updated_at = OLD.updated_at
        BEGIN
          UPDATE files SET updated_at = strftime('%s','now') WHERE id = NEW.id;
        END;
        """)
        self.conn.commit()

    def close(self):
        try:
            self.cur.close()
            self.conn.close()
        except Exception:
            pass

    def create(self,path:str) -> bool:
        try:
            path,name,case_key,ext,size,mtime,ctime = cracker(path)
            now = int(time.time())

            # 开始
            self.cur.execute("BEGIN")
            self.cur.execute("""
            INSERT INTO files (path, name, case_key, ext, size, mtime, ctime, deleted, updated_at)
            VALUES (?,?,?,?,?,?,?,0,?)
            """,(path, name, case_key, ext, size, int(mtime), int(ctime), now))
            self.conn.commit()
            print("Inserted file finish")
            return True
        except Exception as e:
            self.conn.rollback()
            error(f_name,"create",e)
            return False

    def create_dir(self,dir_path:str) -> bool:
        try:
            p = Path(dir_path).resolve()
            if not p.exists() or not p.is_dir():
                print(f"[create_dir] 路径不存在或不是目录: {p}")
                return False

            st = p.stat()
            path_norm = os.path.normpath(str(p))  # 规范绝对路径
            name = p.name
            case_key = name.lower()
            ext = ""  # 目录无扩展名
            size = 0  # 目录大小置 0
            mtime = int(st.st_mtime)
            ctime = int(st.st_ctime)
            updated_at = int(time.time())

            # 目录入库
            self.cur.execute("BEGIN")
            self.cur.execute("""
            INSERT INTO files (path, name, case_key, ext, size, mtime, ctime, deleted, updated_at)
            VALUES (?,?,?,?,?,?,?,1,?)
            """,(path_norm, name, case_key, ext, size, mtime, ctime, updated_at))
            self.conn.commit()
            print(f"[create_dir] inserted/ignored: {path_norm}")
            return True
        except Exception as e:
            try:
                self.conn.rollback()
            except:
                pass
            error("db_tools.py", "create_dir", e)
            return False

    def delete(self,path:str) -> bool:
        try:
            norm = os.path.normpath(path)
            self.cur.execute("DELETE FROM files WHERE path = ?",(norm,))
            self.conn.commit()
            return True
        except Exception as e:
            error(f_name,"delete",e)
            return False


    def update(self,old_path:str,new_path:str) -> bool:
        try:
            # 重新计算字段
            path,name,case_key,ext,size,mtime,ctime = cracker(new_path)
            now = int(time.time())

            # 定位需要改变的记录
            old_norm = os.path.normpath(old_path)

            # 开始
            self.cur.execute("BEGIN")
            self.cur.execute("""
                        UPDATE files SET
                            path = ?,
                            name = ?,
                            case_key = ?,
                            ext = ?,
                            size = ?,
                            mtime = ?,
                            ctime = ?,
                            deleted = 0,
                            updated_at = ?
                        WHERE path = ?
                    """, (path, name, case_key, ext, size, int(mtime), int(ctime), now, old_norm))
            self.conn.commit()

            if self.cur.rowcount:
                print(f"✅ updated: {old_norm} -> {path}  (rows: {self.cur.rowcount})")
            return True
        except Exception as e:
            self.conn.rollback()
            error(f_name,"update",e)
            return False

    def update_many(self,old_paths:list[str],new_path_dir:str,old_path_dir:str) -> bool:
        """输入的old_path全部经过normpath清洗, old_path_dir: 目标/  而new_path_dir: 新目标/"""
        pairs = [(path,path.replace(old_path_dir,new_path_dir,1)) for path in old_paths]
        now = int(time.time())

        try:
            self.cur.execute("BEGIN")

            # 创建临时表
            self.cur.execute("""
            CREATE TEMP TABLE IF NOT EXISTS temp_dirs(
            dir     TEXT PRIMARY KEY,
            new_dir TEXT NOT NULL
            )
            """)

            # 保证临时表里没有缓存
            self.cur.execute("""
            DELETE FROM temp_dirs
            """)

            # 对临时表批量插入更新路径
            self.cur.executemany("""
            INSERT OR REPLACE INTO temp_dirs(dir,new_dir) VALUES (?,?)""",pairs)

            # 根据临时表更改正式表
            self.cur.execute("""
            UPDATE files
            SET path = (SELECT new_dir FROM temp_dirs WHERE dir = files.path),
                updated_at = ?
            WHERE EXISTS (SELECT 1 FROM temp_dirs WHERE dir = files.path)
            """,(now,))

            # 清空临时表
            self.cur.execute("""
            DELETE FROM temp_dirs""")

            self.conn.commit()
            print("修改成功")
            return True
        except Exception as e:
            self.conn.rollback()
            print("Error from update tool update_many function in db_tools: ",e)
            return False

    def custom_instruction(self,instruction:str):
        try:
            instruction = instruction.replace("\\\\", "\\")
            self.cur.execute(instruction)
            if instruction.lower().startswith("select"):
                print("接受到的指令:",instruction)
                output = self.cur.fetchall()
                self.conn.commit()
            else:
                self.conn.commit()
                output = f"Affected rows: {self.cur.rowcount}"
            return output
        except Exception as e:
            print("Error from custom instruction in db_tools: ",e)

    def list_file_and_dir_paths(self,path: str) -> list[str]:
        path = os.path.normpath(path)
        like_pattern = path + os.sep + "%"
        self.cur.execute("BEGIN")
        self.cur.execute("""
        SELECT path FROM files WHERE path LIKE?""",(like_pattern,))

        row = self.cur.fetchall()
        output = [each[0] for each in row]
        output.append(path)
        self.conn.commit()
        return output

    def reset_db(self) -> bool:
        "清空数据库"
        print("开始清空数据库信息...")
        file_list = []

        try:
            self.cur.execute("BEGIN")
            self.cur.execute("DELETE FROM files")
            self.conn.commit()
            return True
        except Exception as e:
            self.conn.rollback()
            error(f_name,"reset_db",e)
            return False

