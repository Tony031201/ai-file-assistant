from __future__ import annotations
import pandas as pd
from dataclasses import dataclass,asdict
import re, warnings

DATE_WARN = "Could not infer format"
ISO8601_RE = re.compile(r"^\d{4}-\d{2}-\d{2}([Tt ].*)?$")
YMD8_RE    = re.compile(r"^\d{8}$")  # 20240131

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

def is_epoch_like(s: pd.Series) -> bool:
    v = pd.to_numeric(s, errors="coerce").dropna()
    if v.empty: return False
    lens = v.astype("int64").astype(str).str.len()
    if lens.mode().empty: return False
    L = int(lens.mode().iat[0])
    if L not in (10, 13): return False  # 秒/毫秒
    unit = "s" if L == 10 else "ms"
    parsed = pd.to_datetime(v.astype("int64"), unit=unit, errors="coerce", utc=True)
    return parsed.notna().mean() > 0.9

def is_yyyymmdd_like(s: pd.Series) -> bool:
    ss = s.astype(str).str.strip()
    if not (ss.str.match(r"^\d{8}$").mean() > 0.9):
        return False
    parsed = pd.to_datetime(ss, format="%Y%m%d", errors="coerce", utc=True)
    return parsed.notna().mean() > 0.9

# —— 可调阈值 —— #
TIME_PARSE_RATIO = 0.80     # ≥80% 可解析成时间 → time
NUM_PARSE_RATIO  = 0.95     # ≥95% 可解析成数字 → number
CAT_MAX_UNIQUE   = 50       # 类别列最大唯一值个数
CAT_MAX_RATIO    = 0.30     # 类别列最大唯一值占比（相对样本数）
SAMPLE_N         = 500      # 抽样行数（加速）
BOOL_CANON = {"true","false","0","1","yes","no","y","n","t","f"}

@dataclass
class ColProfile:
    name: str
    kind: str                       # 预测类型 time/number/category/boolean/text
    na_ratio: float
    nunique: int
    nunique_ratio: float
    dt_ratio: float  # 可解析为时间的比例
    num_ratio: float  # 可解析为数字的比例
    bool_like: bool  # 是否布尔候选（0/1/true/false 等）
    identifier_like: bool  # 是否疑似ID（唯一值极多）

def _sample(series:pd.Series,n=SAMPLE_N) -> pd.Series:
    """抽样n个样本进行分析，如果样本总数不如n，则全部样本用于分析"""
    s = series
    if len(s)>n:
        s = s.sample(n,random_state=42)
    return s

def _is_bool_like(s: pd.Series) -> bool:
    """推测这一列是否为bool类型·"""
    ss = _sample(s).dropna()            #去除缺失值
    if ss.empty:
        return False                    #该列全是缺失值，返回false
    vals = set(ss.unique().tolist())    #提取这一列里的所有唯一值，然后转换为普通的python列表
    # 如果vals的值全在{"true","false","0","1","yes","no","y","n","t","f"}或[0,1]，那么返回True,否则False
    return vals.issubset(BOOL_CANON) or vals.issubset([0,1])

def _bool_normalize_ratio(s: pd.Series) -> float:
    """计算布尔值在数列中的比例"""
    # 数据抽样，并且清理
    ss = _sample(s).dropna().astype(str).str.strip().str.lower()
    if ss.empty:
        return 0.0
    # 返回布尔值在其中占据的比例
    return (ss.isin(BOOL_CANON)).mean()

def _to_datetime_ratio(s: pd.Series) -> float:
    """返回时间项在数列中的比例"""
    ss = _sample(s)
    dt = parse_datetime_safe(ss)
    return float(dt.notna().mean())

def _to_numeric_ratio(s: pd.Series) -> float:
    """返回数字值在数列中的比例"""
    ss = _sample(s)
    num = pd.to_numeric(ss, errors="coerce")
    return float(num.notna().mean())

def _is_identifier_like(s: pd.Series) -> bool:
    """查看该列的内容是不是唯一值"""
    ss = _sample(s)
    nunique = ss.nunique(dropna=True)       # 计算样本中唯一值的数量
    name = str(s.name or "").lower()
    name_hint = any(k in name for k in ["id", "uuid", "guid", "key", "code"])
    # 假如nunique的长度接近ss的90%，则视此列为id列
    return len(ss)>0 and (nunique/len(ss) > 0.9) or name_hint

def infer_schema(df: pd.DataFrame) -> list[ColProfile]:
    """返回每一列的指标与预测类型"""
    profiles: list[ColProfile] = []
    n = len(df)
    for col in df.columns:
        s = df[col]
        na_ratio = float(_sample(s).isna().mean())
        dt_ratio = _to_datetime_ratio(s)
        num_ratio = _to_numeric_ratio(s)
        bool_like = _is_bool_like(s) or _bool_normalize_ratio(s) >= 0.95
        nunique = int(_sample(s).nunique(dropna=True))
        nunique_ratio = float(nunique / max(1,min(len(s),SAMPLE_N)))
        identifier_like = _is_identifier_like(s)

        # 分类决策
        # 先布尔
        if bool_like:
            kind = "boolean"

        # 时间（字符串时间 or 数字时间）
        elif dt_ratio >= TIME_PARSE_RATIO:
            kind = "time"
        elif num_ratio >= NUM_PARSE_RATIO and (is_epoch_like(s) or is_yyyymmdd_like(s)):
            kind = "time"

        # 数值
        elif num_ratio >= NUM_PARSE_RATIO:
            kind = "number"

        # 类别
        elif 2 <= nunique <= min(CAT_MAX_UNIQUE, int(CAT_MAX_RATIO * max(1, n))):
            kind = "category"
        else:
            kind = "text"

        profiles.append(ColProfile(
            name=str(col),
            kind=kind,
            na_ratio=na_ratio,
            nunique=nunique,
            nunique_ratio=nunique_ratio,
            dt_ratio=dt_ratio,
            num_ratio=num_ratio,
            bool_like=bool_like,
            identifier_like=identifier_like
        ))
    return profiles

def infer_col_types(df: pd.DataFrame) -> dict[str,str]:
    """接口：返回 {列名: 类型}，基于 infer_schema 的决策。"""
    return {p.name: p.kind for p in infer_schema(df)}

def schema_as_dicts(df: pd.DataFrame) -> list[dict]:
    """方便打印/日志：把画像结果转为 list[dict]"""
    return [asdict(p) for p in infer_schema(df)]

