# BPMN → mCRL2 方法对比说明

## 三种路径

| 路径 | 命令/脚本 | 是否经 Petri Net | BPMN 语义由谁负责 |
| --- | --- | --- | --- |
| **本方法（推荐）** | `bpmn2pnml_local.py` + `pnml2mcrl2.py` | ✅ 显式 PNML | 本地 BPMN-aware 映射 |
| **网页一键** | `bpmn2mcrl2_web.py` | ⚠️ 有 PNML 但黑盒 | bpmn2petrinet.com 通用映射 |
| **直接 BPMN→mCRL2** | （本项目未实现） | ❌ 跳过 | 需一次性编码全部 BPMN 语义 |

---

## 核心区别（一句话）

**本方法不是跳过中间层，而是把 Petri Net 当作「可检查、可修正的语义桥梁」；网页一键路径虽然也能产出 mCRL2，但在 PNML 层用通用规则处理协作语义，Pizza 上会出现支付互等与行为丢失。**

---

## 对比图（PPT 可直接插入）

| 图 | 文件 | 内容 |
| --- | --- | --- |
| 三路径架构对比 | [`05_three_way_comparison.svg`](05_three_way_comparison.svg) | 本方法 vs 网页一键 vs 概念上的直接转换 |
| 语义可达性柱状对比 | [`06_reachability_comparison.svg`](06_reachability_comparison.svg) | 5 项关键行为 + 结构规模 |
| 本地 vs 网页详图 | [`04_local_vs_web.svg`](04_local_vs_web.svg) | 答辩要点文字版 |
| 仓库详图 | [`../runs/.../05_local_vs_web_summary.svg`](../runs/pizza_official_redownload_20260518/05_local_vs_web_summary.svg) | 原始对照实验输出 |

---

## 本方法 vs 网页一键（官方 Pizza 实测）

| 维度 | 本方法 | 网页一键 |
| --- | --- | --- |
| PNML 规模 | 27 / 23 / 56 | 24 / 18 / 46 |
| LTS states | 200 | 54 |
| receive_payment | ✅ | ❌ |
| calm_customer | ✅ | ❌ |
| joined end | ✅ | ❌ |
| message flow | gating 策略，避免互等 | 机械前置，Pay↔Receive 环路 |
| event gateway | 显式 choose_* | 折叠 |
| timer | 需先选分支 | 可凭空触发 |

---

## 本方法 vs 「直接 BPMN→mCRL2」

若完全跳过 Petri Net，从 BPMN XML 直接生成 mCRL2 进程：

**优点（理论）：** 少一个中间文件，链路更短。

**缺点（本项目未采用的原因）：**

1. BPMN 与 mCRL2 抽象层次差距大，缺少独立语义检查点
2. 协作流程中的 message flow、gateway 选择在 Petri 网中有成熟映射，便于调试
3. `pnml2mcrl2.py` 可复用于任意 PNML（含手工修正后的网）
4. 无法在 PNML 层对比、 diff、可视化 Petri 结构

因此本项目采用 **BPMN → PNML → mCRL2**，并在 **第一层** 做 BPMN-aware 修正，而非一次性直译。

---

## 重新生成对照数据

```bash
python scripts/compare_pizza_local_vs_web.py
```

输出：`docs/runs/pizza_official_redownload_20260518/05_local_vs_web_summary.svg`
