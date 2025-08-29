模块名称: visualization

功能概述
- 数据自动可视化流水线（零配置）：
  1) determine.py —— 列画像与类型推断（time/number/category/boolean/text）
  2) gen_candidates.py —— 基于画像自动生成候选图规格 (Spec)
  3) scorer.py —— 候选图打分排序（启发式评分）
  4) renderer.py —— 按规格渲染图到 PNG（必要时可扩展 SVG）
  5) pipeline.py —— 串联：读取→画像→候选→打分→渲染（Top-N）
  6) interface.py —— 对外接口，调用 pipeline 并在本机打开图片

目录结构
visualization/
├─ determine.py
├─ gen_candidates.py
├─ scorer.py
├─ renderer.py
├─ pipeline.py
└─ interface.py

依赖
- pandas, numpy, matplotlib
- （可选）scikit-learn（renderer 的 PCA 优先使用 sklearn，缺失则退化为 SVD）
- Python 标准库: json, os, dataclasses, re, warnings, typing, math
- 项目内部: data.meta_data.BASE_DIR, core.error_handler.error
- 运行系统：interface.py 使用 os.startfile 打开图片（Windows）。Linux/macOS 请改用 xdg-open/open。

------------------------------------------------------------
1) determine.py（列画像与类型推断）
------------------------------------------------------------
功能
- 识别列类型：time / number / category / boolean / text
- 画像指标：缺失率、唯一值个数/占比、可解析时间/数字比例、布尔候选、疑似 ID

主要对象/函数
- ColProfile(dataclass)
- parse_datetime_safe(series)
- is_epoch_like(series), is_yyyymmdd_like(series)
- infer_schema(df) -> list[ColProfile]
- infer_col_types(df) -> dict[col, kind]
- schema_as_dicts(df) -> list[dict]

阈值（可调）
- TIME_PARSE_RATIO=0.80, NUM_PARSE_RATIO=0.95
- CAT_MAX_UNIQUE=50, CAT_MAX_RATIO=0.30
- SAMPLE_N=500

------------------------------------------------------------
2) gen_candidates.py（生成候选图表规格）
------------------------------------------------------------
功能
- 基于画像与原始 DataFrame，生成未排序的候选图规格（dict）：
  - type: line / facets / bar / box / hist / scatter / heatmap / corr / pca_scatter
  - x, y, hue, agg, resample, topk, bins, sample, notes

核心逻辑
- _best_time / _best_num / _best_two_nums / _best_cat：挑选优质列
- _infer_freq：T/H/D/W/M
- _infer_agg：rate/ratio/avg/mean/pct→mean；含 id/uuid/code/key→count；默认 sum
- _smart_bins / _smart_sample_size：直方图 bins、散点采样量

入口
- gen_candidates(df, profiles) -> List[Dict]

------------------------------------------------------------
3) scorer.py（候选图打分与排序）
------------------------------------------------------------
目的
- 为每个候选图计算一个启发式分数，并据此排序，默认还可对“同类型”去重（保留最高分）。

权重（可调）
- W_BASE：不同图型的基础分
  - line 0.70, bar 0.65, hist 0.60, scatter 0.55, box 0.50, heatmap 0.55, facets 0.60, corr 0.55, pca_scatter 0.50
- 额外加分：
  - W_TIME_BONUS=0.20：时间维图（line/facets）
  - W_POINTS=0.10：点位数处于理想区间（20~500）
  - W_CAT_CARD=0.10：类别基数合适（3~12）
  - W_Y_MISSING=0.05：Y 缺失率低
  - W_TOPK_COVER=0.05：TopK 覆盖率高（≥70%）
  - W_BINS_HIST=0.05：直方图样本量合适（500~100k）

关键函数
- score_candidate(df, spec) -> float
  组合基础分 + 时间加成 + 点位区间 + 类别基数 + Y 缺失 + TopK 覆盖率 + 直方图样本量，裁剪到 [0, 1.5]
- rank_candidates(df, specs, topn=3, dedup_same_type=True) -> List[(spec, score)]
  对候选打分排序；可选择“同类型去重”（默认开启）

实现要点
- 点位估计：不同图按其特性估计可视点数量（如 line 用时间跨度/频率估算，bar/box/heatmap 用类别数，scatter 用采样量）
- TopK 覆盖率：bar/box/heatmap 中，头部 TopK 对总量的覆盖比例 ≥ 70% 给予加分

------------------------------------------------------------
4) renderer.py（按规格渲染图）
------------------------------------------------------------
职责
- 根据 Spec.type 分派到对应渲染函数，输出 PNG 路径。
- 支持：line, facets, bar, box, hist, scatter, heatmap, corr, pca_scatter

公共工具
- parse_datetime_safe：安全时间解析（抑制 “Could not infer format”）
- _apply_topk：类别 TopK 聚合（尾部归为“其他”）
- _alpha_by_n：散点透明度随样本量自适应
- _title_from_spec：标题 = TYPE + notes

入口
- render_chart(df, spec, out_path=None) -> str

------------------------------------------------------------
5) pipeline.py（自动化总入口）
------------------------------------------------------------
auto_visualize(file_path: str, topn=3, out_dir="out", save_svg=False) -> Dict
流程
- 读文件：支持 .csv/.tsv/.json/.ndjson/.jsonl（行式 JSON；否则对 list/dict 归一化）
- 画像：schema_as_dicts(df)
- 候选：gen_candidates(df, profiles)
- 打分：rank_candidates(df, specs, topn)
- 渲染：render_chart(df, spec, out_path)
返回
{
  "charts": [{"spec": dict, "score": float, "png": str, "svg": str|None}, ...],
  "schema": [列画像],
  "why": ["存在时间列+数值列 → 趋势优先", "存在类别+数值 → 分类聚合", "多数值列 → 关系/相关性图"]
}

说明
- _ensure_dir(out_dir)：保证输出目录存在
- save_svg=True 目前仅占位；如需 SVG，建议在 renderer 内同步保存

------------------------------------------------------------
6) interface.py（对外接口）
------------------------------------------------------------
visualization(file_path: str) -> bool
- 强制 matplotlib 使用 "Agg" 后端（无界面环境也可渲染）
- 自动设置中文字体（CANDIDATE_FONTS），并避免负号乱码
- 调用 auto_visualize(..., topn=3, out_dir="out")
- 打印每张图的得分、类型、输出路径；Windows 下用 os.startfile 打开 PNG
- 返回 True/False；异常通过 core.error_handler.error 记录

跨平台
- Windows: os.startfile
- macOS: subprocess.run(["open", PNG_PATH])
- Linux: subprocess.run(["xdg-open", PNG_PATH])

------------------------------------------------------------
快速开始
------------------------------------------------------------
示例一（对外接口）
```python
from visualization.interface import visualization
ok = visualization(r"D:\data\sales.csv")
print("done?", ok)





实际思路:

# 第一步，查看数据的格式
打开数据表，查看每一列是什么内容
规则:

一堆能转成时间的 → 时间列

基本全是数字 → 数值列

就几个有限的值（男/女，国家=US/CA/JP） → 类别列

只有 0/1、True/False → 布尔列

其他乱七八糟文字 → 文本列



# 第二步，生成候选图
时间 + 数值 → 折线图（看趋势）

类别 + 数值 → 条形图（看对比）

两个数值 → 散点图（看关系）

单个数值 → 直方图（看分布）

类别 + 数值 → 箱线图（看离群点）

两个类别 → 热力图（看交叉情况）

很多数值列 → 相关矩阵 / PCA 降维散点




# 第三步，打分排序
有时间列 → 趋势图加分

类别数量合适（3~12 个） → 条形图加分

样本量合适（20~500 个点） → 折线/散点加分

缺失少 → 加分

Top-K 覆盖率高（前10类别占总量 80%） → 加分




# 第四步，统一生成规范输出
{
  "type": "line",
  "x": "date",
  "y": "amount",
  "agg": "sum",
  "resample": "M",
  "notes": "按月汇总销售额趋势"
}

# 第五步，渲染器画图
按要求读数据

聚合/采样

调用 matplotlib/seaborn 画图

保存成图片，返回路径




样本:
原始数据:
date, amount, category
2024-01-01, 120, Book
2024-01-02, 90, Food
2024-01-03, 150, Tech


列类型识别

date → time

amount → number

category → category

候选图

line(date, amount)

bar(category, sum(amount))

facets_line(date, amount | by=category)

hist(amount)

打分

line: 0.9

bar: 0.85

facets_line: 0.8

hist: 0.6

选定 Spec（top3）

[
  {"type":"line","x":"date","y":"amount","agg":"sum","resample":"D","notes":"每日销售额趋势"},
  {"type":"bar","x":"category","y":"amount","agg":"sum","topk":10,"notes":"Top10 类别销售额"},
  {"type":"hist","x":"amount","bins":30,"notes":"销售额分布"}
]

画图, 输出三张图，返回图片路径给用户。

