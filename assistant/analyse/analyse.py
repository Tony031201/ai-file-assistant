from core.error_handler import error
from analyse.analyse_claud import ClaudClient

def _read_file(file_path:str) -> str:
    # 该函数读取本地中的文件内容
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            return content
    except FileNotFoundError as e:
        error(r"analyse\analyse","_read_file",e)

def analyze(purpose:str,file_path:str) -> str:
    try:
        # 该函数负责调用ai分析代码
        # 首先读取文件信息
        content = _read_file(file_path)

        # 建立api链接
        analyzer = ClaudClient()

        # 将文件信息和目的传入api，获得分析结果
        output = analyzer.send_message(purpose + " : " + content)
        return output
    except Exception as e:
        error(r"analyse\analyse","analyze",e)

# def test():
#     output = analyze("你帮我分析一下这个文件大概是有什么作用","path/to/your/file.py")
#     print(output)
# test()