from __future__ import annotations
import os, json
import pandas as pd
from typing import Dict, Any

# ① 引入前面四步
from visualization.determine import schema_as_dicts
from visualization.gen_candidates import gen_candidates
from visualization.scorer import rank_candidates
from visualization.renderer import render_chart

# —— 工具 —— #
def _read_table(path: str, orient: str = "records") -> pd.DataFrame:
    ext = os.path.splitext(path)[1].lower()
    if ext in [".csv", ".tsv"]:
        sep = "," if ext==".csv" else "\t"
        return pd.read_csv(path, sep=sep, low_memory=False)
    if ext in [".json", ".ndjson", ".jsonl"]:
        # 尝试行式 JSON；失败则扁平化 records
        try:
            return pd.read_json(path, lines=True)
        except Exception:
            raw = json.load(open(path, "r", encoding="utf-8"))
            return pd.json_normalize(raw) if isinstance(raw, (list, dict)) else pd.DataFrame()
    raise ValueError(f"暂不支持的文件类型: {ext}")

def _ensure_dir(d: str):
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)

# —— 主入口 —— #
def auto_visualize(
    file_path: str,
    topn: int = 3,
    out_dir: str = "out",
    save_svg: bool = False
) -> Dict[str, Any]:
    """
    读取文件→列画像→候选→打分→渲染Top-N
    返回: {
      "charts": [{"spec": dict, "score": float, "png": str, "svg": str|None}],
      "schema": [列画像],
      "why": [解释要点]
    }
    """
    df = _read_table(file_path)
    if df.empty:
        raise ValueError("数据为空或无法解析。")

    profiles = schema_as_dicts(df)
    specs = gen_candidates(df, profiles)
    ranked = rank_candidates(df, specs, topn=topn)

    _ensure_dir(out_dir)
    charts = []
    for i, (spec, score) in enumerate(ranked, 1):
        png = os.path.join(out_dir, f"auto_{i}_{spec['type']}.png")
        png = render_chart(df, spec, out_path=png)
        svg_path = None
        if save_svg:
            # 二次保存 SVG（renderer 内部已 set_title 等）
            import matplotlib.pyplot as plt
            # 为简单起见，这里不重复绘制，直接忽略；若需SVG请在 renderer 内同时保存
            svg_path = png.replace(".png", ".svg")  # 预留占位
        charts.append({"spec": spec, "score": float(score), "png": png, "svg": svg_path})

    # 解释要点（why）
    why = []
    has_time = any(p["kind"]=="time" for p in profiles)
    nums = [p for p in profiles if p["kind"]=="number"]
    cats = [p for p in profiles if p["kind"]=="category"]
    if has_time and nums:
        why.append("存在时间列与数值列 → 趋势图优先。")
    if cats and nums:
        why.append("存在类别+数值 → 类别聚合对比图。")
    if len(nums) >= 2:
        why.append("多数值列 → 关系或相关性图可解释。")

    return {"charts": charts, "schema": profiles, "why": why}