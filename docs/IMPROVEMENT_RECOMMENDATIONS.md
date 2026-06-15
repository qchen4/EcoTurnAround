# EcoTurnaround OS — 改进建议总结

本文档汇总了对 **EcoTurnaround OS** 黑客松项目在 **UI**、**数据可视化**、**公开数据集** 三个方向的可落地改进建议。  
目标：在不破坏现有后端闭环的前提下，提升 demo 说服力、评委理解速度与产品专业感。

> **边界不变：** 仍为 synthetic ATL-sandbox prototype；不使用真实 Delta/ATL 运营数据；不声称全局最优。

---

## 1. 项目现状判断（简要）

### 已经很强的部分

- **完整闭环**：自然语言目标 → 场景 → baseline → optimized → metrics → verifier → bottleneck → refinement → memory → UI
- **诚实叙事**：主动暴露 tradeoff（CO2e/成本改善，waste 回归，lateness 保持）
- **工程克制**：Pydantic schema、模块边界、135 tests、确定性 demo、无外部 API 依赖
- **T11 UI 方向正确**：从 pipeline dashboard 升级为 decision intelligence cockpit

### 当前展示层的主要缺口

1. **空间感**：缺少机场 zone / 路径的可视化
2. **时间感**：缺少 schedule timeline（Gantt）对比
3. **外部可信度锚点**：缺少公开数据 calibration 的明确说明（非冒充真数据）

---

## 2. UI 改进建议

T11 的信息架构已经正确（先回答“该做什么、为什么”）。下一步重点是 **3 秒内让评委看懂故事**，而不是增加更多 tab。

### 2.1 Decision Brief 再产品化

| 建议 | 说明 |
|------|------|
| **Decision Banner** | 顶部固定一句推荐决策，例如：`Adopt optimized dispatch + raise freshness priority`，旁附 Confidence 与 Verifier PASS |
| **Tradeoff 视觉化** | 除文字 tradeoff 外，用绿/红/灰对比：`Carbon ↓` / `Cost ↓` / `Reliability ↔` / `Waste ↑` |
| **Human-gate 统一样式** | 所有 safety-critical 提案用固定红色边框卡片，文案统一为 “Never auto-relax” |

### 2.2 减少工程师语言

主界面用 **business label**，技术 ID 仅留在 Technical Appendix：

| 技术 change | 业务表述 |
|-------------|----------|
| `solver:freshness_priority` | Prioritize catering freshness |
| `staging:reserve_catering_vehicle_near_catering_facility` | Pre-stage catering truck |
| `policy:prefer_electric_when_margins_allow` | Prefer EV when safe |

### 2.3 What-if Workspace 更像对话

- 增加 **Suggested follow-up questions** 按钮，例如：
  - “Why did waste increase?”
  - “How to fix catering delay?”
  - “Can we relax safety boundaries?”
- 点击后自动填入 what-if 框并展示解读（仍不 rerun optimizer）

### 2.4 侧边栏增强

在 sidebar 增加 **Run Summary**：

- Scenario name
- Random seed
- Last run timestamp（可选）
- Reflection `attempt_id`

提升“可追溯、可复盘”的专业感。

---

## 3. 数据可视化改进建议

当前以 metric cards 和 tables 为主，适合 demo，但缺少 **机场运营感**。以下改进均可基于现有 `schedule`、`scenario`、`ZONE_COORDS` 在 **UI 层聚合**，无需改 optimizer/verifier/memory。

### 3.1 最高优先级（P0）

#### A. ATL-sandbox 运营示意图（Zone Graph）

**不是乘客地铁图，而是 ground-ops zone graph（运营示意图）。**

你们已有图结构：

- **节点**：`DEFAULT_ZONES`（terminal、concourse、cargo、charging hub 等）
- **边**：`travel_times` 矩阵
- **布局**：`ZONE_COORDS`（合成 2D 坐标）

建议三层叠加：

```
Layer 1 — 静态拓扑（常驻）
  - 20 个 zone 节点
  - concourse 西→东主线 + 主要连接

Layer 2 — 运行态（Run 之后）
  - 节点大小 ∝ task count 或 CO2e load
  - 节点颜色 ∝ zone 类型或 bottleneck severity
  - 边粗细 ∝ 实际通行频次或总 travel time

Layer 3 — 决策叙事（可选高亮）
  - worst_late_task 路径
  - worst_freshness_waste: catering_facility → concourse
  - restricted_runway_crossing（红色禁行）
  - future_autonomy_corridor（虚线通道）
```

**借鉴地铁图之处：** concourse 链、hub 连接、分区挂接  
**保留机场感之处：** 标注 catering/cargo/charging/restricted，不用乘客站符号

**放置位置：** Decision Brief 或 Evidence & Confidence  
**实现：** `st.scatter_chart`、`matplotlib` + `st.pyplot`，或可选 `pydeck`；MVP 不必加 plotly

#### B. Baseline vs Optimized 并排对比图

避免 stacked bar，使用 **grouped bar** 或并排 metric：

```
CO2e   [==== baseline 100 ====] [== optimized 31 ==]
Cost   [==== baseline 100 ====] [== optimized 83 ==]
Waste  [==== baseline 100 ====] [===== optimized 106 =====]
```

配文：

> Baseline = 100. Lower is better. Values above 100 indicate regression.

直接视觉化你们最强的故事：**减排成功，但 waste 诚实回归**。

### 3.2 次优先级（P1–P2）

#### C. Schedule Timeline（Gantt）

用 `DispatchEvent.start_time_min` / `end_time_min`：

- 横轴：时间
- 纵轴：vehicle
- 颜色：task type 或 powertrain

用途：解释 optimizer 如何把任务分给 EV，以及 catering 为何变慢（waste 上升的视觉证据）。

#### D. CO2e 分解图

在现有 by-powertrain / by-task-type 表格基础上增加：

- baseline vs optimized 的 powertrain 占比对比（饼图或条形图）
- Top 5 emitting tasks 条形图

所有图标注：**Synthetic CO2e proxy, not real emissions.**

### 3.3 可视化原则（黑客松）

- 主屏最多 **1–2 张故事图**，其余放 expander
- 颜色语义固定：绿=改善，红=回归，灰=不变，橙=风险
- 不为了炫技全站 plotly；若加 plotly，仅用于 1–2 个关键交互图

### 3.4 关于 plotly

- `requirements.txt` 当前无 plotly
- **答辩前不必强行引入**；Streamlit 原生图表 + scatter 足够
- 若需 hover/zoom，可后续仅对 zone graph 或 Gantt 添加

---

## 4. 公开数据集建议

公开数据的价值是 **校准 sandbox 参数与叙事可信度**，不是替换为“真实 Delta 数据”。

### 4.1 推荐话术

> **Public data calibrates the sandbox; it does not replace operational truth.**

UI 可展示：

> ATL-sandbox parameters calibrated from public references; all dispatch results remain synthetic.

### 4.2 适合的数据源（按性价比）

| 优先级 | 数据源 | 用途 | 不用于 |
|--------|--------|------|--------|
| 高 | **OpenStreetMap / Overpass** | ATL 区域 POI、道路、terminal 相对位置 → 校准 `ZONE_COORDS` | 真实车队位置 |
| 高 | **FAA / 机场公开示意图** | concourse/terminal 结构 inspiration | 实时运行数据 |
| 高 | **DOE AFDC** | 充电桩类型、功率范围 → 校准 charger 参数 | 真实充电队列 |
| 中 | **ICAO / FAA / EPA GSE 可持续公开报告** | 问题陈述、行业趋势（pitch/Devpost） | 直接灌入 simulator KPI |
| 中 | **IATA / 机场可持续报告** | 叙事支撑 | 冒充运营绩效 |
| 慎用 | **BTS On-Time / OpenSky** | 任务 `release/deadline` 分布校准 | 声称 Delta 实时调度 |
| 慎用 | 机场 EV 充电公开 listings | charger 数量与 zone 分布 | 真实利用率 |

### 4.3 推荐集成方式（轻量）

新增文档与目录（不改变核心 schema）：

```
data/calibration/          # 可选：存放公开参考参数
docs/DATA_PROVENANCE.md    # 数据来源、用途、边界
```

`DATA_PROVENANCE.md` 示例条目：

```text
Source: FAA airport diagram (layout inspiration)
Source: DOE AFDC (charger power ranges)
Source: ICAO ground ops sustainability brief (problem framing)
Usage: parameter calibration only
Not used: real fleet, real schedules, real emissions
```

### 4.4 不建议的做法

- 将公开航班数据称为 “Delta operational data”
- 用真实坐标 + 真实航班 + 真实 KPI 却不标注 synthetic/proxy
- 为“像真数据”破坏 deterministic demo 稳定性

---

## 5. ATL 图网络：概念澄清

### 问题：是否把 ATL 抽象成图网络？类似地铁？

**答：是图网络，但最佳形态是「机场地面运营示意图」，不是乘客地铁图。**

| 维度 | 地铁图风格 | 运营示意图（推荐） |
|------|------------|-------------------|
| 节点 | 等距、符号化 | 按 `ZONE_COORDS` 相对摆放 |
| 边 | 直线连接 | 实际/主要 travel 路径 |
| 语义 | 乘客换乘 | GSE 任务流、充电、restricted zone |
| 目标 | 看懂连通 | 看懂运营瓶颈与决策含义 |

### 与当前 default run 的叙事衔接

图上可高亮两条路径：

1. **Carbon win**：diesel 活动减少，EV 在 concourse ↔ charging hub 活动增加  
2. **Waste risk**：`catering_facility → concourse_X` 链路耗时变长  

对应 Decision Brief 一句话：

> Emissions improved because electric dispatch shifted activity toward cleaner corridors; waste risk rose because catering pickup paths became longer.

---

## 6. 实施优先级路线图

若时间有限，建议按以下顺序推进（**均可 mostly UI-only**）：

| 优先级 | 任务 | 预期效果 |
|--------|------|----------|
| **P0** | ATL zone 运营示意图 + 运行态叠加 | 3 秒建立“机场地面运营”认知 |
| **P0** | Baseline vs Optimized 并排 KPI/条形对比 | tradeoff 视觉化，强化诚实叙事 |
| **P1** | `docs/DATA_PROVENANCE.md` + UI 一句 calibration 说明 | 提升 research 深度与可信度 |
| **P1** | Decision Brief business labels + human-gate 卡片样式 | 降低评委认知负担 |
| **P2** | Schedule Gantt（baseline vs optimized） | 解释 waste 为何变差 |
| **P2** | What-if suggested questions | UI 更像 copilot |
| **P3** | plotly 交互、OSM 精细校准 | 锦上添花 |

---

## 7. 与赛道（Moving Things & People）的对应

| 赛道子主题 | UI/可视化/数据如何支撑 |
|------------|------------------------|
| Port & Airport Sustainability | Zone graph + CO2e breakdown + 减排对比图 |
| Supply Chain Visibility & Efficiency | 路径可视化 + Gantt + Evidence board |
| EV Charging Experience | Charging hub 节点高亮 + SOC/energy 相关 bottleneck 卡片 |

---

## 8. 实施边界（保持不变）

以下 **不需要改** 即可做大部分上述改进：

- `baseline.py` / `optimizer.py` / `verifier.py` / `analysis.py` / `refinement.py` / `memory.py` 逻辑
- `schemas.py` 数据契约（除非仅为 UI 聚合加可选 helper）
- 确定性 seed demo 行为

主要改动面：

- `app.py`（可视化组件、文案、布局）
- `docs/DATA_PROVENANCE.md`（新建）
- 可选：轻量 `ecoturn/viz_helpers.py`（只读聚合，放在 UI 侧或薄 helper 模块）

---

## 9. 一句话总结

**EcoTurnaround OS 的后端闭环和决策叙事已经很强；下一步最高 ROI 的改进是：把已有的 zone graph 和 schedule 画出来，把 tradeoff 画清楚，并用公开数据做诚实的 calibration 说明——而不是去追求更多算法或更多 tab。**

---

*文档版本：T11 之后建议汇总 · 供黑客松答辩前迭代参考*
