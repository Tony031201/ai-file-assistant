import os
from core.error_handler import error

def createFile(file_path:str,content:str) -> bool:
    try:
        directory = os.path.dirname(file_path)

        # 确保目录存在
        os.makedirs(directory, exist_ok=True)

        # 如果文件已存在则返回 False
        if os.path.exists(file_path):
            return False

        # 导入文件内容
        with open(file_path,"w",encoding="utf-8") as f:
            f.write(content)
        return True
    except Exception as e:
        error("generate/create_file","createFile",e)
        return False