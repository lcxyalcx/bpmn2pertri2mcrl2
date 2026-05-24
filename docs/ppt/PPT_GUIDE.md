# PPT 制作素材指南

本目录提供 **16:9（1280×720）** 可直接插入 PowerPoint / Keynote 的 SVG 图，以及仓库内其他高价值可视化资源索引。

---

## 推荐幻灯片结构（10 页）

| 页码 | 标题建议 | 推荐素材 | 文件路径 |
| --- | --- | --- | --- |
| 1 | 封面 / 项目简介 | 流水线总览 | [`01_pipeline.svg`](01_pipeline.svg) |
| 2 | 研究背景：官方 Pizza | BPMN 示意图 + 规模统计 | [`../runs/pizza_official_redownload_20260518/pizza_official_source.png`](../runs/pizza_official_redownload_20260518/pizza_official_source.png) + [`../runs/.../02_bpmn_summary.svg`](../runs/pizza_official_redownload_20260518/02_bpmn_summary.svg) |
| 3 | 转换流水线 | 四步流程图 | [`../runs/.../01_pipeline.svg`](../runs/pizza_official_redownload_20260518/01_pipeline.svg) |
| 4 | BPMN → PNML | Petri 网结构概览 | [`../runs/.../03_pnml_overview.svg`](../runs/pizza_official_redownload_20260518/03_pnml_overview.svg) |
| 5 | PNML → mCRL2 | 动作与状态映射示意 | [`../visuals/pizza_mcrl2_structure.svg`](../visuals/pizza_mcrl2_structure.svg) + [`../runs/.../04_mcrl2_summary.svg`](../runs/pizza_official_redownload_20260518/04_mcrl2_summary.svg) |
| 6 | BPMN 元素支持范围 | 支持矩阵 | [`02_bpmn_support.svg`](02_bpmn_support.svg) |
| 7 | 性质验证结果 | 6 项检查摘要 | [`03_verification_results.svg`](03_verification_results.svg) 或 [`../verification/pizza_official/pizza_official_verification_summary.svg`](../verification/pizza_official/pizza_official_verification_summary.svg) |
| 8 | LTS 状态空间可视化 | 部分状态图（200 状态） | [`../verification/pizza_official/pizza_official_bounded_lts.svg`](../verification/pizza_official/pizza_official_bounded_lts.svg) |
| 9 | 本地 vs 网页对照 | 语义差异 | [`04_local_vs_web.svg`](04_local_vs_web.svg) 或 [`../runs/.../05_local_vs_web_summary.svg`](../runs/pizza_official_redownload_20260518/05_local_vs_web_summary.svg) |
| 10 | 总结与展望 | 流水线 + 支持范围 | [`01_pipeline.svg`](01_pipeline.svg) + 口头总结 |

---

## 本目录 PPT 专用图（1280×720）

| 文件 | 内容 |
| --- | --- |
| [`01_pipeline.svg`](01_pipeline.svg) | 流水线 + 关键数字（适合封面/总结） |
| [`02_bpmn_support.svg`](02_bpmn_support.svg) | 可转换 / 近似 / 不可转换 三栏 |
| [`03_verification_results.svg`](03_verification_results.svg) | LTS 摘要 + 6 项性质验证 |
| [`04_local_vs_web.svg`](04_local_vs_web.svg) | 本地 vs 网页语义对照 + 答辩要点 |

---

## 插入 PowerPoint 的方法

### macOS / 新版 PowerPoint

1. **插入 → 图片 → 来自文件**，选择 `.svg` 或 `.png`
2. SVG 可无损缩放；若版本较旧，先用浏览器打开 SVG → 截图或导出 PDF 再插入

### 官方 Pizza BPMN 示意图（PNG）

```
docs/runs/pizza_official_redownload_20260518/pizza_official_source.png
```

适合放在「案例介绍」页，直观展示双 participant 协作结构。

---

## 关键数据（可直接复制到 PPT 文本框）

**官方 Pizza BPMN**

- 2 process · 18 flow nodes · 9 tasks · 6 message flows
- 1 parallel gateway · 1 event-based gateway · 3 catch events

**本地 PNML / mCRL2**

- 27 places · 23 transitions · 56 arcs
- 23 个语义化 action

**Bounded LTS**

- 200 states · 199 transitions · 18 action labels
- deterministic: yes

**性质验证（6/6 符合预期）**

- order → vendor ✓
- delivery ✓
- payment ✓
- ask/calm loop ✓
- joined end ✓
- no deadlock（预期 false）✓

**本地 vs 网页**

- 支付可达：本地 ✓ / 网页 ✗
- 安抚循环：本地 ✓ / 网页 ✗
- 联合结束：本地 ✓ / 网页 ✗

---

## 重新生成可视化

```bash
# 性质验证 + LTS SVG
python scripts/check_pizza_official.py

# 完整 pipeline 图（runs 目录）
python scripts/rerun_pizza_official_pipeline.py

# 本地 vs 网页对照图
python scripts/compare_pizza_local_vs_web.py
```

生成后主要输出：

- `docs/verification/pizza_official/pizza_official_verification_summary.svg`
- `docs/verification/pizza_official/pizza_official_bounded_lts.svg`
- `docs/runs/pizza_official_redownload_20260518/01_pipeline.svg` … `05_local_vs_web_summary.svg`

---

## 演讲建议（每页一句话）

1. **封面**：我们实现了 BPMN→Petri Net→mCRL2 的可复现自动化流水线。
2. **案例**：官方 Pizza 是含协作、消息流与网关的经典验证样例。
3. **流程**：四步转换，每步有独立脚本与中间产物。
4. **PNML**：sequence flow 变 place，活动/网关变 transition。
5. **mCRL2**：token 流动语义，action 可追溯到 BPMN 节点。
6. **兼容性**：已支持主流网关、专用任务、子流程与 boundary。
7. **验证**：6 项性质全部符合预期，支付与循环行为可达。
8. **LTS**：200 状态 partial 图展示丰富并发行为。
9. **对照**：本地语义转换优于网页工具，尤其在 message flow 建模上。
10. **总结**：从「能生成 mCRL2」到「可验证、可可视化的协作流程模型」。
