from __future__ import annotations
import numpy as np
import pandas as pd
from typing import List, Dict, Optional
from visualization.determine import infer_schema, infer_col_types
from visualization.determine import parse_datetime_safe, is_epoch_like, is_yyyymmdd_like

def _is_timey_series(df: pd.DataFrame, col: str) -> bool:
    s = df[col]
    dt = parse_datetime_safe(s)
    dt_ratio = dt.notna().mean()
    return (dt_ratio >= 0.8) or is_epoch_like(s) or is_yyyymmdd_like(s)

#默认参数#
TOPK_BAR = 10
TOPK_BOX = 10
TOPK_HEATMAP = 20
BINS_HIST = 30
SAMPLE_SCATTER = 5000

def _best_time(df: pd.DataFrame,time_cols: List[str]) -> str:
    # 选缺失少，解析稳定的时间列
    scores = []
    for c in time_cols:
        s = parse_datetime_safe(df[c])         # 选择时间列
        ok = s.notna().mean()
        span = (s.max() - s.min()) if s.notna().any() else pd.Timedelta(0)
        span_days = span.total_seconds() / 86400 if span is not pd.NaT else 0       # 时间跨度
        scores.append((c, ok + 0.05 * np.log1p(max(span_days, 0))))
    # 挑选分数最高的列作为用于画表的时间列
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[0][0]

def _best_num(df: pd.DataFrame, num_cols: List[str]) -> str:
    # 选缺失少 + 方差较大的数值列
    scores = []
    for c in num_cols:
        s = pd.to_numeric(df[c], errors='coerce')
        na = s.isna().mean()
        var = float(s.var(skipna=True) or 0.0)
        scores.append((c, (1 - na) * (np.log1p(var))))
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[0][0]

def _best_two_nums(df: pd.DataFrame, num_cols: List[str]) -> tuple[str, str]:
    # 选一对相关性|r|较高且各自质量不错的列
    if len(num_cols) == 2:
        return num_cols[0], num_cols[1]
    best, score = (num_cols[0], num_cols[1]), -1
    for i in range(len(num_cols)):
        for j in range(i + 1, len(num_cols)):
            x, y = num_cols[i], num_cols[j]
            xs = pd.to_numeric(df[x], errors="coerce")
            ys = pd.to_numeric(df[y], errors="coerce")
            m = xs.notna() & ys.notna()
            if m.sum() < 30:
                continue
            r = np.corrcoef(xs[m], ys[m])[0, 1]
            s = abs(r) * 0.7 + (1 - xs[m].isna().mean()) * 0.15 + (1 - ys[m].isna().mean()) * 0.15
            if s > score:
                score, best = s, (x, y)
    return best

def _best_cat(df: pd.DataFrame, cat_cols: List[str]) -> str:
    # 选基数合适(3~30)且不极端单一的类别列
    n = len(df)
    cand = []
    for c in cat_cols:
        k = int(df[c].nunique(dropna=True))
        if k < 2:
            continue
        vc = df[c].value_counts(dropna=True)
        top_ratio = float(vc.iloc[0] / max(1, n)) if len(vc) else 1.0
        base = 1.0 - abs((k - 8) / 20)   # 8 附近更理想
        score = base * (1 - max(0.0, top_ratio - 0.6))  # 头部占比>60%降分
        cand.append((c, score))
    if not cand:
        return cat_cols[0]
    cand.sort(key=lambda x: x[1], reverse=True)
    return cand[0][0]

# —— 智能默认参数 —— #
def _infer_freq(series: pd.Series) -> str:
    s = parse_datetime_safe(series).dropna().sort_values()
    if len(s) < 3:
        return "D"
    dt = s.diff().dropna().median()
    if dt <= pd.Timedelta(minutes=2): return "T"
    if dt <= pd.Timedelta(hours=2):   return "H"
    if dt <= pd.Timedelta(days=2):    return "D"
    if dt <= pd.Timedelta(days=14):   return "W"
    return "M"

def _infer_agg(col_name: str) -> str:
    low = col_name.lower()
    if any(k in low for k in ["rate", "ratio", "avg", "mean", "pct"]):
        return "mean"
    if any(k in low for k in ["id", "uuid", "code", "key"]):
        return "count"
    return "sum"

def _smart_bins(series: pd.Series) -> int:
    m = series.dropna().shape[0]
    if m < 1000: return 20
    if m > 100000: return 50
    return BINS_HIST

def _smart_sample_size(n_rows: int) -> int:
    if n_rows <= 5000: return n_rows
    if n_rows <= 100000: return 8000
    return SAMPLE_SCATTER

# —— Spec 构造器 —— #
def spec_line(x: str, y: str, resample: str, agg: str) -> Dict:
    return {"type":"line","x":x,"y":y,"hue":None,"agg":agg,"resample":resample,"topk":None,"bins":None,"sample":None,
            "notes": f"按 {resample} 汇总 {y} 趋势（{agg}）。"}

def spec_facets(x: str, y: str, hue: str, resample: str, agg: str) -> Dict:
    return {"type":"facets","x":x,"y":y,"hue":hue,"agg":agg,"resample":resample,"topk":6,"bins":None,"sample":None,
            "notes": f"{hue} 分面，按 {resample} 汇总 {y} 趋势（{agg}）。"}

def spec_bar(x: str, y: Optional[str], agg: str = "count", topk: int = TOPK_BAR) -> Dict:
    return {"type":"bar","x":x,"y":y,"hue":None,"agg":agg,"resample":"none","topk":topk,"bins":None,"sample":None,
            "notes": f"{x} 的 {('计数' if y is None else f'{y}聚合('+agg+')')} Top-{topk}。"}

def spec_box(x: str, y: str, topk: int = TOPK_BOX) -> Dict:
    return {"type":"box","x":x,"y":y,"hue":None,"agg":"none","resample":"none","topk":topk,"bins":None,"sample":None,
            "notes": f"{x}（Top-{topk} 类别）的 {y} 分布箱线图。"}

def spec_hist(x: str, bins: int) -> Dict:
    return {"type":"hist","x":x,"y":None,"hue":None,"agg":"none","resample":"none","topk":None,"bins":bins,"sample":None,
            "notes": f"{x} 的分布直方图（bins={bins}）。"}

def spec_scatter(x: str, y: str, sample: int) -> Dict:
    return {"type":"scatter","x":x,"y":y,"hue":None,"agg":"none","resample":"none","topk":None,"bins":None,"sample":sample,
            "notes": f"{x} vs {y} 散点（采样 {sample}）。"}

def spec_heatmap(x: str, y: str, agg: str = "count", topk: int = TOPK_HEATMAP) -> Dict:
    return {"type":"heatmap","x":x,"y":y,"hue":None,"agg":agg,"resample":"none","topk":topk,"bins":None,"sample":None,
            "notes": f"{x}×{y} 交叉热力图（{agg}，Top-{topk}）。"}

def spec_corr(cols: List[str]) -> Dict:
    return {"type":"corr","x":cols,"y":cols,"hue":None,"agg":"none","resample":"none","topk":None,"bins":None,"sample":None,
            "notes": f"相关矩阵（数值列：{', '.join(cols[:6])}…）。"}

def spec_pca(hue: Optional[str], sample: int = 10000) -> Dict:
    return {"type":"pca_scatter","x":None,"y":None,"hue":hue,"agg":"none","resample":"none","topk":None,"bins":None,"sample":sample,
            "notes": f"PCA 2D 散点（采样 {sample}，颜色={hue or 'None'}）。"}

# —— 主函数：生成候选图 —— #
def gen_candidates(df: pd.DataFrame, profiles: List[dict]) -> List[Dict]:
    """
    输入：df + 第一步的列画像（list[dict] 或 ColProfile → dict）
    输出：候选 Spec 列表（未排序）
    """
    kinds = {p["name"]: p["kind"] for p in profiles}
    time_cols = [c for c,k in kinds.items() if k=="time"]
    num_cols  = [c for c,k in kinds.items() if k=="number" and not _is_timey_series(df, c)]
    cat_cols  = [c for c,k in kinds.items() if k=="category"]

    cands: List[Dict] = []

    # 趋势：line / facets_line
    if time_cols and num_cols:
        t = _best_time(df, time_cols)
        y = _best_num(df, num_cols)
        fr = _infer_freq(df[t])
        agg = _infer_agg(y)
        cands.append(spec_line(t, y, fr, agg))
        # 类别分面（类数 ≤ 6）
        for c in cat_cols:
            if df[c].nunique(dropna=True) <= 6:
                cands.append(spec_facets(t, y, c, fr, agg))
                break

    # 比较：bar（有数值）/ bar_count（无数值）
    if cat_cols and num_cols:
        x = _best_cat(df, cat_cols)
        y = _best_num(df, num_cols)
        cands.append(spec_bar(x, y, agg=_infer_agg(y), topk=TOPK_BAR))
        if df[x].nunique(dropna=True) >= 3:
            cands.append(spec_box(x, y, topk=min(TOPK_BOX, df[x].nunique())))
    elif cat_cols:
        x = _best_cat(df, cat_cols)
        cands.append(spec_bar(x, None, agg="count", topk=TOPK_BAR))

    # 分布：hist
    if num_cols:
        x = _best_num(df, num_cols)
        bins = _smart_bins(pd.to_numeric(df[x], errors="coerce"))
        cands.append(spec_hist(x, bins))

    # 关系：scatter
    if len(num_cols) >= 2:
        x, y = _best_two_nums(df, num_cols)
        cands.append(spec_scatter(x, y, sample=_smart_sample_size(len(df))))

    # 类别×类别：heatmap
    if len(cat_cols) >= 2:
        a, b = cat_cols[:2]
        if a != b:
            cands.append(spec_heatmap(a, b, agg="count", topk=TOPK_HEATMAP))

    # 高维：corr / pca
    if len(num_cols) >= 6 and len(df) >= 200:
        # 选择方差较大的前10个
        s = [(c, float(pd.to_numeric(df[c], errors="coerce").var(skipna=True) or 0.0)) for c in num_cols]
        s.sort(key=lambda x: x[1], reverse=True)
        cols10 = [c for c,_ in s[:10]]
        if len(cols10) >= 3:
            cands.append(spec_corr(cols10))
        # 选一个基数≤12 的类别作为 hue
        hue = None
        for c in cat_cols:
            if df[c].nunique(dropna=True) <= 12:
                hue = c; break
        cands.append(spec_pca(hue=hue, sample=10000))

    return cands


