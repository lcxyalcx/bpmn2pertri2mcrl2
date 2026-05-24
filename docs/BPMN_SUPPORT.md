# BPMN 元素支持范围

本地转换链路：`bpmn2pnml_local.py` → `pnml2mcrl2.py`

最后更新：2026-05-24

---

## 可转换（✅ 支持）

| 类别 | BPMN 元素 | 映射说明 |
| --- | --- | --- |
| 事件 | `startEvent`, `endEvent` | 流程/消息启动与结束 |
| 事件 | `intermediateCatchEvent` | 消费 sequence + message place |
| 事件 | `intermediateThrowEvent` | 产生 sequence + message place |
| 事件 | `boundaryEvent` | 附着活动输入 place 上可触发的变迁 |
| 活动 | `task` | generic 任务 |
| 活动 | `userTask`, `serviceTask`, `scriptTask`, `manualTask`, `businessRuleTask`, `sendTask`, `receiveTask` | 统一映射为 `task` |
| 活动 | `callActivity` | 按单变迁活动处理 |
| 网关 | `parallelGateway`, `eventBasedGateway`, `exclusiveGateway`, `inclusiveGateway`, `complexGateway` | 见下文网关策略 |
| 容器 | `subProcess`, `adHocSubProcess`, `eventSubProcess`, `transaction` | **展开**内部节点，重连外部 sequenceFlow |
| 流 | `sequenceFlow`, `messageFlow` | place；gating 型消息流进入 Petri 网 |

**PNML → mCRL2：** 合法 PNML 均可转换。

---

## 近似处理（⚠️ 可转换但语义简化）

| 场景 | 行为 |
| --- | --- |
| 网关条件表达式 | 不解析；XOR/OR 按结构展开 |
| 多实例 (`multiInstanceLoopCharacteristics`) | 按**单实例**转换，并给出警告 |
| 子流程 | 扁平化展开，不保留层次作用域 |
| boundary event | 与附着活动**并行**可触发，不区分中断/非中断 |
| timer | 普通 transition，无真实时钟 |
| message flow | 信息型 task-to-task 消息仍可能省略 |

---

## 不可转换（❌ 不支持）

| 类别 | BPMN 元素 | 原因 |
| --- | --- | --- |
| 编排 | `globalTask`, `choreographyTask`, `conversation` 等 | 超出当前过程模型 |
| 数据 | `dataObject`, `dataStore`, data association | 无数据语义（扫描时忽略） |
| 高级语义 | 补偿、资源角色、真实时间约束 | 超出 Petri 网 token 模型 |

---

## 网关映射策略

| 网关 | Petri Net 策略 |
| --- | --- |
| `parallelGateway` | 单 transition，多入多出 |
| `exclusiveGateway` / `eventBasedGateway` / `complexGateway` | 每个 (入边, 出边) 一条 `choose_*` |
| `inclusiveGateway` split | 出边非空子集 → `activate_*` |
| `inclusiveGateway` join | 入边非空子集 → `join_*` |

---

## 快速检查

```bash
python scripts/check_bpmn_compatibility.py path/to/model.bpmn
python -m unittest discover -s tests -v
```
