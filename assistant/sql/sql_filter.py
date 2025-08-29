import re
from typing import TypedDict

class Output(TypedDict):
    """sql为输出的sql，status表示是否通过过滤器"""
    sql:str
    status:bool

# 黑名单
BANNED = [
    " pragma ", " with ", " drop ", " truncate ", " delete ", " insert ",
    " alter ", " create ", " attach ", " detach ", " vacuum ", " reindex ",
    " union ", " intersect ", " except ", " returning "
]

def SQL_Filter(sql:str) -> Output:
    # 数据清洗
    text = sql.replace("\r\n", " ").replace("\n", " ").strip()
    s = f" {text.lower()} "

    # 排除未授权指令
    if any(k in s for k in BANNED):
        return {"sql": text, "status": False}

    # 仅允许 select / update
    if s.lstrip().startswith("select"):
        # 只允许 from files
        if " from files " not in s:
            return {"sql": text, "status": False}
        if re.search(r"\bfrom\s+files\s*,", s):
            return {"sql": text, "status": False}
        return {"sql": text, "status": True}

    if s.lstrip().startswith("update"):
        # 必须是 update files
        if not s.lstrip().startswith("update files"):
            return {"sql": text, "status": False}

        # 抽出 set 与 where（跨行/多空白）
        m = re.search(r"\bupdate\s+files\s+set\s+(?P<set>.*?)\s+\bwhere\b\s+(?P<where>.+)$",
                      s, flags=re.DOTALL)
        if not m:
            return {"sql": text, "status": False}

        set_clause = m.group("set").strip()

        # 只能修改 note，且 SET 中不允许逗号（防多列）
        if "," in set_clause:
            return {"sql": text, "status": False}
        if re.match(r"^note\s*=", set_clause) is None:
            return {"sql": text, "status": False}

        # 额外防护：SET 子句里不能出现其它列名（避免误改）
        forbidden_cols = [" path ", " name ", " case_key ", " ext ", " size ",
                          " mtime ", " ctime ", " deleted ", " updated_at "]
        sc_pad = " " + set_clause + " "
        if any((" " + col.strip() + " ") in sc_pad for col in [c.strip() for c in forbidden_cols]):
            return {"sql": text, "status": False}

        return {"sql": text, "status": True}

    # 其他语句一律拒绝
    return {"sql": text, "status": False}

# print(SQL_Filter("select path,size from files where ext='.py' and deleted=0;")   )          # ✅
# print(SQL_Filter("select * from files join other on 1=1;")                                 )# ✅
# print(SQL_Filter("update files set note='日志' where ext='.log' and deleted=0;")  )          # ✅
# print(SQL_Filter("update files set note='a', name='x' where id=1;")              )          # ❌（多列）
# print(SQL_Filter("update files set size=0 where id=1;")                          )          # ❌（非 note）
# print(SQL_Filter("update other set note='a' where id=1;")                        )          # ❌（非 files）
# print(SQL_Filter("update files set note='a';")                                   )          # ❌（无 WHERE）
# print(SQL_Filter("update files set note='a' where id = 1;")                      )          # ✅