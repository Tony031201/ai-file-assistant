import re
from typing import TypedDict

# 解析器, 从模型文本中提取 回答/指令/sql
SQL_FENCE_RE = re.compile(r"```sql\s*(.*?)```", re.IGNORECASE | re.DOTALL)

class Response(TypedDict):
    answer:str
    instruction:str
    file_path: str
    file_content: str
    cmd_command: str
    sql:str

def parse_response(raw_text: str) -> dict:
    """
    解析固定格式输出：
    回答: ...
    指令: ...
    文件路径: ...
    生成文件内容: ...
    SQL:
    ```sql
    ...（可为空）
    ```
    也兼容行内 SQL：SQL: <到文本末尾>
    返回: {"answer": str, "instruction": str, "sql": str}（sql 可能为 ""）
    """
    # 统一换行，方便跨平台
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")

    # 1) 回答：直到出现“指令:”为止（允许中间无换行）
    m_answer = re.search(r"回答:\s*(.*?)(?=\n?\s*指令:)", text, flags=re.DOTALL)
    answer = (m_answer.group(1).strip() if m_answer else None)

    # 2) 指令：直到出现“参数块:”为止
    m_instr = re.search(r"指令:\s*(.*?)(?=\n?\s*参数块:)", text, flags=re.DOTALL)
    instruction = (m_instr.group(1).strip() if m_instr else None)

    # 参数块整体截取（从“参数块:”到文本末尾）
    m_param = re.search(r"参数块:\s*(.*?)(?=\n?\s*文件路径:)", text, flags=re.DOTALL)
    if not m_param:
        raise ValueError("❌ 缺少『参数块:』段。")
    param_text = m_param.group(1).strip()

    # 3) 文件路径：直到出现“生成文件内容:”为止
    m_filep = re.search(r"文件路径:\s*(.*?)(?=\n?\s*生成文件内容:)", text, flags=re.DOTALL)
    file_path = (m_filep.group(1).strip() if m_filep else None)

    # 4) 生成文件内容：直到出现"系统命令:"为止
    c_file = re.search(r"生成文件内容:\s*(.*?)(?=\n?\s*系统命令:)", text, flags=re.DOTALL)
    file_content = (c_file.group(1).strip() if c_file else None)

    # 5) 系统命令：直到出现"可执行SQL:"为止
    m_cmd = re.search(r"系统命令:\s*(.*?)(?=\n?\s*可执行SQL:)", text, flags=re.DOTALL)
    cmd_command = (m_cmd.group(1).strip() if m_cmd else None)

    # 6) SQL：优先取 ```sql 代码块
    sql = None
    m_fence = SQL_FENCE_RE.search(text)
    if m_fence:
        sql_block = m_fence.group(1).strip()
        # 去掉以 -- 开头的行注释
        cleaned = "\n".join(line for line in sql_block.splitlines() if not line.strip().startswith("--")).strip()
        sql = cleaned  # 可能是空字符串 ""
    else:
        # 兼容行内 可执行SQL：SQL: 后面直到文本结尾
        m_inline = re.search(r"可执行SQL:\s*(.*)$", text, flags=re.DOTALL | re.IGNORECASE)
        if m_inline:
            sql_inline = m_inline.group(1).strip()
            sql = sql_inline  # 行内可能非空

    # 7) 严格校验：六段都必须存在（SQL和cmd_command 允许为空字符串，但不能是 None）
    if answer is None or instruction is None or file_path is None or file_content is None or cmd_command is None or sql is None:
        raise ValueError("❌ 模型输出格式不完整：必须包含『回答:』『指令:』『文件路径:』『生成文件内容:』『系统命令:』『SQL:』六段。")

    return {"answer": answer, "instruction": instruction,"file_path": file_path, "file_content":file_content, "cmd_command": cmd_command, "sql": sql}



def merge_response(response:Response):
    return f"回答: {response['answer']} 指令: {response['instruction']} 文件路径: {response['file_path']} 生成文件内容:{response['file_content']} 系统命令: {response['cmd_command']} 可执行SQL: {response['sql']}"


