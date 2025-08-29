from __future__ import annotations
import pandas as pd
from typing import Dict, List, Tuple, Optional

# —— 权重（可调） —— #
W_BASE = {
    "line": 0.70, "bar": 0.65, "hist": 0.60, "scatter": 0.55,
    "box": 0.50, "heatmap": 0.55, "facets": 0.60, "corr": 0.55, "pca_scatter": 0.50
}
W_TIME_BONUS   = 0.20   # 有时间维的加分（线型/分面）
W_POINTS       = 0.10   # 点位处于理想区间的加分
W_CAT_CARD     = 0.10   # 类别基数合适（3~12）的加分
W_Y_MISSING    = 0.05   # Y 列缺失少的加分
W_TOPK_COVER   = 0.05   # TopK 覆盖率高的加分
W_BINS_HIST    = 0.05   # 直方图样本量合适的加分

IDEAL_POINTS_LOW  = 20
IDEAL_POINTS_HIGH = 500

def _interval_score(v: float, low: float, high: float, weight: float) -> float:
    if v <= 0:
        return 0.0
    if v < low:
        return weight * (v / low)
    if v > high:
        return weight * max(0.0, (2*high - v) / high)  # 超出越多降分
    return weight

def _estimate_points(df: pd.DataFrame, spec: Dict) -> int:
    t = spec["type"]
    if t == "line":
        x = spec.get("x")
        freq = spec.get("resample", "D")
        ser = pd.to_datetime(df[x], errors="coerce", utc=True).dropna()
        if ser.empty:
            return 0
        span = ser.max() - ser.min()
        denom = {
            "T": pd.Timedelta(minutes=1),
            "H": pd.Timedelta(hours=1),
            "D": pd.Timedelta(days=1),
            "W": pd.Timedelta(weeks=1),
            "M": pd.Timedelta(days=30),
        }.get(freq, pd.Timedelta(days=1))
        return max(1, int(span / denom))
    if t in ("bar", "box", "heatmap"):
        x = spec.get("x")
        if x in df.columns:
            return int(min(50, df[x].nunique(dropna=True)))
        return 0
    if t == "hist":
        return spec.get("bins") or 30
    if t == "scatter":
        return int(min(len(df), spec.get("sample", 5000)))
    if t in ("corr", "pca_scatter"):
        return 10
    return 0

def _cat_card_score(df: pd.DataFrame, spec: Dict) -> float:
    x = spec.get("x")
    if x in df.columns:
        k = int(df[x].nunique(dropna=True))
        return _interval_score(k, low=3, high=12, weight=W_CAT_CARD)
    return 0.0

def _y_missing_score(df: pd.DataFrame, spec: Dict) -> float:
    y = spec.get("y")
    if y and y in df.columns:
        return (1.0 - float(pd.Series(df[y]).isna().mean())) * W_Y_MISSING
    return 0.0

def _topk_coverage_score(df: pd.DataFrame, spec: Dict) -> float:
    if spec["type"] not in ("bar", "box", "heatmap"):
        return 0.0
    x, y, agg, topk = spec.get("x"), spec.get("y"), spec.get("agg"), spec.get("topk", 10)
    if x not in df.columns:
        return 0.0
    s = df[x]
    if y and y in df.columns and (agg or "sum"):  # 有 y 列的 bar/box/heatmap
        vals = pd.to_numeric(df[y], errors="coerce")
        g = vals.groupby(s).sum(min_count=1)  # 这里默认 sum；评分阶段只求覆盖率
        g = g.sort_values(ascending=False)
    else:
        g = s.value_counts()
    if g.empty:
        return 0.0
    top = g.head(topk).sum()
    cov = float(top / max(1, g.sum()))
    return (cov >= 0.7) * W_TOPK_COVER  # 覆盖率≥70% 加满分；否则不给

def _time_bonus(spec: Dict) -> float:
    return W_TIME_BONUS if spec["type"] in ("line", "facets") else 0.0

def _hist_sample_score(df: pd.DataFrame, spec: Dict) -> float:
    if spec["type"] != "hist":
        return 0.0
    x = spec.get("x")
    if x not in df.columns:
        return 0.0
    m = pd.to_numeric(df[x], errors="coerce").dropna().shape[0]
    # 样本 500~100k 给加分
    if 500 <= m <= 100000:
        return W_BINS_HIST
    # 边缘范围按比例递减
    if m < 500:
        return W_BINS_HIST * (m / 500)
    if m > 100000:
        return W_BINS_HIST * max(0.0, (200000 - m) / 100000)
    return 0.0

def score_candidate(df: pd.DataFrame, spec: Dict) -> float:
    base = W_BASE.get(spec["type"], 0.50)
    s = base
    # 时间优待
    s += _time_bonus(spec)
    # 点位评分
    pts = _estimate_points(df, spec)
    s += _interval_score(pts, IDEAL_POINTS_LOW, IDEAL_POINTS_HIGH, W_POINTS)
    # 类别基数评分
    if spec["type"] in ("bar", "box", "heatmap"):
        s += _cat_card_score(df, spec)
        s += _topk_coverage_score(df, spec)
    # Y 缺失评分
    s += _y_missing_score(df, spec)
    # 直方图样本量评分
    s += _hist_sample_score(df, spec)
    # 裁剪到 [0, 1.5]（纯预防）
    return float(max(0.0, min(1.5, s)))

def rank_candidates(df: pd.DataFrame, specs: List[Dict], topn: int = 3, dedup_same_type: bool = True) -> List[Tuple[Dict, float]]:
    scored = [(spec, score_candidate(df, spec)) for spec in specs]
    ranked = sorted(scored, key=lambda x: x[1], reverse=True)
    if not dedup_same_type:
        return ranked[:topn]
    # 同类型去重（保留分数最高的一个）
    seen, out = set(), []
    for spec, sc in ranked:
        t = spec["type"]
        if t in seen:
            continue
        out.append((spec, sc))
        seen.add(t)
        if len(out) >= topn:
            break
    return out