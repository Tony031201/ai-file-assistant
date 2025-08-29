from visualization.pipeline import auto_visualize
import os
import matplotlib
from data.meta_data import BASE_DIR
from core.error_handler import error

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib import font_manager as fm

# 1) 明确设置中文字体（任选其一存在的字体）
CANDIDATE_FONTS = [
    r"C:\Windows\Fonts\msyh.ttc",   # 微软雅黑（推荐）
    r"C:\Windows\Fonts\simhei.ttf", # 黑体
    r"C:\Windows\Fonts\msyh.ttf",
    r"C:\Windows\Fonts\SimSun.ttc", # 宋体
]
font_path = next((p for p in CANDIDATE_FONTS if os.path.exists(p)), None)
if font_path:
    fm.fontManager.addfont(font_path)
    font_name = fm.FontProperties(fname=font_path).get_name()
    plt.rcParams["font.family"] = font_name

# 2) 关闭坐标轴负号乱码
plt.rcParams["axes.unicode_minus"] = False



def visualization(file_path:str) -> bool:
    try:
        res = auto_visualize(
            file_path,
            topn=3, out_dir="out", save_svg=False)
        for c in res["charts"]:
            print(f"{c['score']:.3f} → {c['spec']['type']} → {c['png']}")
            PNG_DIR = os.path.join(BASE_DIR, f"{c['png']}")
            os.startfile(PNG_DIR)
        print("why:", "; ".join(res["why"]))
        return True
    except Exception as e:
        error("visualization/visualization", "visualization", e)
        return False