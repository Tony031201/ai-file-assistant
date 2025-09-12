import sys,json,os,shutil
from pathlib import Path
from summarize.Claude_client_final import ClaudClient2

def read_json_from_analyse():
    # 局部分析储存的地址(分析以txt形式储存)
    json_target = Path(__file__).parent.parent/"analyse"/"store"
    txt_list = []

    # 记录局部分析的文件地址
    try:
        for f in json_target.iterdir():
            if f.is_file():
                txt_list.append(f)
    except Exception as e:
        print("错误来自project_analyse read_json.py:",e)

    return txt_list

def analyze_overall(txt_list:[Path]):
    # 将局部分析加载进全局分析
    if len(txt_list) == 0:
        return
    zip_json = {}
    try:
        for txt in txt_list:
            with open(txt,"r",encoding="utf-8") as f:
                content = json.load(f)
                filename = content["file"]
                summary = content["summary"]
                key_symbols = content.get("key_symbols",[])[:2]
                risks = content.get("risks",[])[:1]

                zip_json[filename] = {
                    "summary": summary,
                    "key_symbols": key_symbols,
                    "risks": risks,
                }
        return zip_json
    except Exception as e:
        print(e)
        sys.exit(1)

def run_summarize():
    api_config_path = Path(__file__).parent.parent.parent/"data"/"config.json"
    config = None
    with open(api_config_path,"r",encoding="utf-8") as f:
        config = json.load(f)
    if config["SONIC_4_API_KEY_2"]:
        SONIC_4_API_KEY_2 = config["SONIC_4_API_KEY_2"]
    else:
        print("config.json文件缺失对应字段")
        sys.exit(1)
    client = ClaudClient2(API_KEY=SONIC_4_API_KEY_2)

    txt_list = read_json_from_analyse()
    zip_json = analyze_overall(txt_list)
    result = client.send_message(zip_json)

    with open("result.txt","w",encoding="utf-8") as f:
        f.write(result)

    json_target = Path(__file__).parent.parent / "analyse" / "store"
    # 删除整个目录
    shutil.rmtree(json_target)

    # 重建空目录
    json_target.mkdir(parents=True, exist_ok=True)

