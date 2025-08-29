# renderer.py
from __future__ import annotations
import os, math, warnings, re
from typing import Dict, Optional, Tuple, List
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# —— 安全时间解析（复用我们在前面定义的思路） —— #
DATE_WARN = "Could not infer format"
ISO8601_RE = re.compile(r"^\d{4}-\d{2}-\d{2}([Tt ].*)?$")
YMD8_RE    = re.compile(r"^\d{8}$")

def parse_datetime_safe(obj: pd.Series) -> pd.Series:
    s = obj.astype(str).str.strip()
    if (s.str.match(YMD8_RE).mean() > 0.9):
        return pd.to_datetime(s, format="%Y%m%d", errors="coerce", utc=True)
    if (s.str.match(ISO8601_RE).mean() > 0.7):
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=DATE_WARN)
            return pd.to_datetime(s, errors="coerce", utc=True)
    try:
        return pd.to_datetime(s, errors="coerce", utc=True, format="mixed")
    except TypeError:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=DATE_WARN)
            return pd.to_datetime(s, errors="coerce", utc=True)

# —— 小工具 —— #
def _ensure_dir(path: str):
    d = os.path.dirname(os.path.abspath(path))
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)

def _title_from_spec(spec: Dict) -> str:
    t = spec.get("type","").upper()
    n = spec.get("notes") or ""
    return f"{t}: {n}" if n else t

def _agg_series(s: pd.Series, how: str):
    how = (how or "sum").lower()
    if how == "mean": return s.mean()
    if how == "count": return s.count()
    return s.sum()  # 默认 sum

def _apply_topk(df: pd.DataFrame, col: str, k: int) -> pd.Series:
    vc = df[col].value_counts(dropna=False)
    if k is None or k <= 0 or len(vc) <= k:
        return df[col]
    keep = set(vc.index[:k].tolist())
    return df[col].apply(lambda v: v if v in keep else "其他")

def _to_numeric(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")

def _alpha_by_n(n: int) -> float:
    # 点多时自动降低透明度
    if n <= 2000: return 0.8
    if n <= 10000: return 0.5
    return 0.3

# —— 各图型渲染 —— #
def render_line(df: pd.DataFrame, spec: Dict, out: Optional[str]) -> str:
    x, y = spec["x"], spec["y"]
    resample = spec.get("resample", "D")
    agg = (spec.get("agg") or "sum").lower()

    t = parse_datetime_safe(df[x])
    v = _to_numeric(df[y])
    m = t.notna() & v.notna()
    ts = pd.DataFrame({x: t[m], y: v[m]}).set_index(x)

    if resample and resample.lower() != "none":
        g = getattr(ts[y].resample(resample), agg)()
    else:
        g = ts[y]

    fig, ax = plt.subplots(figsize=(8,4.2))
    ax.plot(g.index, g.values, linewidth=1.8)
    ax.set_title(_title_from_spec(spec))
    ax.set_xlabel(x); ax.set_ylabel(f"{agg}({y})" if resample!="none" else y)
    ax.grid(True, alpha=0.25)
    plt.tight_layout()
    out = out or f"chart_line_{x}_{y}.png"
    _ensure_dir(out); plt.savefig(out, dpi=150); plt.close(fig)
    return out

def render_facets(df: pd.DataFrame, spec: Dict, out: Optional[str]) -> str:
    x, y, hue = spec["x"], spec["y"], spec["hue"]
    resample = spec.get("resample","W")
    agg = (spec.get("agg") or "sum").lower()

    t = parse_datetime_safe(df[x])
    v = _to_numeric(df[y])
    c = df[hue].astype(str)
    m = t.notna() & v.notna() & c.notna()
    sub = pd.DataFrame({x:t[m], y:v[m], hue:c[m]})

    cats = sub[hue].value_counts().index.tolist()
    cats = cats[:min(6, len(cats))]  # 最多6面板
    n = len(cats)
    cols = min(3, n); rows = math.ceil(n/cols)

    fig, axes = plt.subplots(rows, cols, figsize=(5*cols, 3.2*rows), squeeze=False)
    for i, cat in enumerate(cats):
        r, cidx = divmod(i, cols)
        ax = axes[r][cidx]
        ss = sub[sub[hue]==cat].set_index(x)[y]
        g = getattr(ss.resample(resample), agg)()
        ax.plot(g.index, g.values, linewidth=1.6)
        ax.set_title(str(cat))
        ax.grid(True, alpha=0.25)
    for j in range(n, rows*cols):
        r, cidx = divmod(j, cols); axes[r][cidx].axis("off")
    fig.suptitle(_title_from_spec(spec), y=0.98)
    plt.tight_layout()
    out = out or f"chart_facets_{x}_{y}_{hue}.png"
    _ensure_dir(out); plt.savefig(out, dpi=150); plt.close(fig)
    return out

def render_bar(df: pd.DataFrame, spec: Dict, out: Optional[str]) -> str:
    x, y, agg, topk = spec["x"], spec.get("y"), (spec.get("agg") or "count").lower(), spec.get("topk") or 10
    cat = _apply_topk(df, x, topk)
    if y:
        vals = _to_numeric(df[y])
        sub = pd.DataFrame({x:cat, y:vals}).dropna()
        g = sub.groupby(x)[y].agg(agg).sort_values(ascending=False).head(topk)
    else:
        g = cat.value_counts().head(topk)

    fig, ax = plt.subplots(figsize=(7.5,4.2))
    ax.bar(g.index.astype(str), g.values)
    ax.set_title(_title_from_spec(spec)); ax.set_xlabel(x); ax.set_ylabel((agg if y else "count"))
    ax.tick_params(axis='x', rotation=20)
    ax.grid(True, axis='y', alpha=0.25)
    plt.tight_layout()
    out = out or f"chart_bar_{x}_{y or 'count'}.png"
    _ensure_dir(out); plt.savefig(out, dpi=150); plt.close(fig)
    return out

def render_hist(df: pd.DataFrame, spec: Dict, out: Optional[str]) -> str:
    x, bins = spec["x"], spec.get("bins") or 30
    v = _to_numeric(df[x]).dropna()
    fig, ax = plt.subplots(figsize=(7.5,4.2))
    ax.hist(v.values, bins=bins)
    ax.set_title(_title_from_spec(spec)); ax.set_xlabel(x); ax.set_ylabel("count")
    ax.grid(True, alpha=0.25)
    plt.tight_layout()
    out = out or f"chart_hist_{x}.png"
    _ensure_dir(out); plt.savefig(out, dpi=150); plt.close(fig)
    return out

def render_box(df: pd.DataFrame, spec: Dict, out: Optional[str]) -> str:
    x, y, topk = spec["x"], spec["y"], spec.get("topk") or 10
    cat = _apply_topk(df, x, topk).astype(str)
    v = _to_numeric(df[y])
    sub = pd.DataFrame({x:cat, y:v}).dropna()
    order = sub[x].value_counts().index.tolist()
    data = [sub[sub[x]==k][y].values for k in order]
    fig, ax = plt.subplots(figsize=(7.5,4.2))
    ax.boxplot(data, labels=[str(k) for k in order], showfliers=False)
    ax.set_title(_title_from_spec(spec)); ax.set_xlabel(x); ax.set_ylabel(y)
    ax.tick_params(axis='x', rotation=20)
    ax.grid(True, axis='y', alpha=0.25)
    plt.tight_layout()
    out = out or f"chart_box_{x}_{y}.png"
    _ensure_dir(out); plt.savefig(out, dpi=150); plt.close(fig)
    return out

def render_scatter(df: pd.DataFrame, spec: Dict, out: Optional[str]) -> str:
    x, y = spec["x"], spec["y"]
    sample = spec.get("sample") or min(len(df), 5000)
    xs, ys = _to_numeric(df[x]), _to_numeric(df[y])
    sub = pd.DataFrame({x:xs, y:ys}).dropna()
    if len(sub) > sample:
        sub = sub.sample(sample, random_state=42)
    fig, ax = plt.subplots(figsize=(7.2,4.4))
    ax.scatter(sub[x].values, sub[y].values, s=12, alpha=_alpha_by_n(len(sub)))
    ax.set_title(_title_from_spec(spec)); ax.set_xlabel(x); ax.set_ylabel(y)
    ax.grid(True, alpha=0.25)
    plt.tight_layout()
    out = out or f"chart_scatter_{x}_{y}.png"
    _ensure_dir(out); plt.savefig(out, dpi=150); plt.close(fig)
    return out

def render_heatmap(df: pd.DataFrame, spec: Dict, out: Optional[str]) -> str:
    x, y, topk = spec["x"], spec["y"], spec.get("topk") or 20
    cx = _apply_topk(df, x, topk).astype(str)
    cy = _apply_topk(df, y, topk).astype(str)
    tab = pd.crosstab(cy, cx)  # 行=y, 列=x
    mat = tab.values
    fig, ax = plt.subplots(figsize=(6 + 0.2*mat.shape[1], 5 + 0.2*mat.shape[0]))
    im = ax.imshow(mat, aspect='auto')
    ax.set_xticks(range(mat.shape[1])); ax.set_xticklabels(tab.columns, rotation=30, ha='right')
    ax.set_yticks(range(mat.shape[0])); ax.set_yticklabels(tab.index)
    ax.set_title(_title_from_spec(spec))
    plt.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    plt.tight_layout()
    out = out or f"chart_heatmap_{x}_{y}.png"
    _ensure_dir(out); plt.savefig(out, dpi=150); plt.close(fig)
    return out

def render_corr(df: pd.DataFrame, spec: Dict, out: Optional[str]) -> str:
    cols = spec.get("x") if isinstance(spec.get("x"), list) else None
    if not cols:
        cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    sub = df[cols].apply(pd.to_numeric, errors="coerce")
    corr = sub.corr(method="pearson", min_periods=20)
    mat = corr.values
    fig, ax = plt.subplots(figsize=(6 + 0.2*mat.shape[1], 5 + 0.2*mat.shape[0]))
    im = ax.imshow(mat, vmin=-1, vmax=1, cmap="bwr")
    ax.set_xticks(range(mat.shape[1])); ax.set_xticklabels(corr.columns, rotation=30, ha='right')
    ax.set_yticks(range(mat.shape[0])); ax.set_yticklabels(corr.index)
    ax.set_title(_title_from_spec(spec))
    plt.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    plt.tight_layout()
    out = out or f"chart_corr.png"
    _ensure_dir(out); plt.savefig(out, dpi=150); plt.close(fig)
    return out

def render_pca(df: pd.DataFrame, spec: Dict, out: Optional[str]) -> str:
    hue = spec.get("hue")
    sample = spec.get("sample") or 10000
    # 选数值列
    num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    X = df[num_cols].apply(pd.to_numeric, errors="coerce").dropna()
    if len(X) == 0 or X.shape[1] < 2:
        raise ValueError("PCA: 没有可用的数值列")
    if len(X) > sample:
        X = X.sample(sample, random_state=42)
    # 标准化
    Xn = (X - X.mean()) / X.std(ddof=0)
    # PCA（优先 sklearn）
    try:
        from sklearn.decomposition import PCA
        comp = PCA(n_components=2).fit_transform(Xn.values)
    except Exception:
        # 无 sklearn：SVD 退化
        U, S, Vt = np.linalg.svd(np.nan_to_num(Xn.values), full_matrices=False)
        comp = (U[:, :2] * S[:2])
    fig, ax = plt.subplots(figsize=(6.8, 4.6))
    if hue and hue in df.columns:
        h = df.loc[X.index, hue].astype(str)
        cats = h.value_counts().index[:12].tolist()
        for cat in cats:
            m = (h == cat).values
            ax.scatter(comp[m,0], comp[m,1], s=10, alpha=0.6, label=str(cat))
        ax.legend(loc="best", fontsize=8, ncol=min(3, len(cats)))
    else:
        ax.scatter(comp[:,0], comp[:,1], s=10, alpha=0.6)
    ax.set_title(_title_from_spec(spec)); ax.set_xlabel("PC1"); ax.set_ylabel("PC2")
    ax.grid(True, alpha=0.25)
    plt.tight_layout()
    out = out or f"chart_pca.png"
    _ensure_dir(out); plt.savefig(out, dpi=150); plt.close(fig)
    return out

# —— 入口：根据 spec.type 分派 —— #
DISPATCH = {
    "line": render_line,
    "facets": render_facets,
    "bar": render_bar,
    "hist": render_hist,
    "box": render_box,
    "scatter": render_scatter,
    "heatmap": render_heatmap,
    "corr": render_corr,
    "pca_scatter": render_pca,
}

def render_chart(df: pd.DataFrame, spec: Dict, out_path: Optional[str] = None) -> str:
    t = spec.get("type")
    if t not in DISPATCH:
        raise ValueError(f"未知图型: {t}")
    return DISPATCH[t](df, spec, out_path)
