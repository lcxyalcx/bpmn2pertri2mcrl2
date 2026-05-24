# BPMN 元素支持范围

本地转换链路：`bpmn2pnml_local.py` → `pnml2mcrl2.py`

最后更新：2026-05-24

---

## 可转换（✅ 支持）

| 类别 | BPMN 元素 | Petri Net / mCRL2 映射 | 备注 |
| --- | --- | --- | --- |
| 事件 | `startEvent` | transition；消费 start place 或 message place | 支持消息触发启动 |
| 事件 | `endEvent` | transition；产生 process end place | 支持多 participant join |
| 事件 | `intermediateCatchEvent` | transition；消费 sequence + message place | timer 等按普通 catch 处理 |
| 事件 | `intermediateThrowEvent` | transition；产生 sequence + message place | 抛出全部 outgoing messageFlow |
| 活动 | `task` | transition；消费/产生 sequence 与 gating message place | 仅 generic `task` |
| 网关 | `parallelGateway` | transition；AND-split / AND-join | 单变迁多入多出 |
| 网关 | `eventBasedGateway` | 多个 `choose_*` transition | 每个 (入边, 出边) 一条路径 |
| 网关 | `exclusiveGateway` | 多个 `choose_*` transition | XOR split/join；不解析条件表达式 |
| 网关 | `inclusiveGateway` | `activate_*` / `join_*` 或 `route_*` transition | OR split/join；按出边/入边子集展开 |
| 网关 | `complexGateway` | 同 `exclusiveGateway` | 保守处理 |
| 流 | `sequenceFlow` | place | 控制流容器 |
| 流 | `messageFlow` | place（gating 型） | 信息型 task-to-task 消息不作为接收前置条件 |

**PNML → mCRL2：** 凡能生成合法 PNML 的 Petri 网，均可由 `pnml2mcrl2.py` 转换为 mCRL2。

**已验证样例：** 官方 Pizza 协作流程、简化线性 `pizza.bpmn`、含 XOR/OR 网关与 throw 事件的单元测试用例。

---

## 不可转换（❌ 不支持）

| 类别 | BPMN 元素 | 原因 |
| --- | --- | --- |
| 网关条件 | 网关上的条件表达式 / default flow | 未解析 BPMN 条件语言 |
| 子结构 | `subProcess` | 子流程未展开 |
| 子结构 | `callActivity` | 调用活动未建模 |
| 子结构 | `transaction` / `adHocSubProcess` / `eventSubProcess` | 高级结构未建模 |
| 事件 | `boundaryEvent` | 边界中断/取消未建模 |
| 任务类型 | `userTask` / `serviceTask` / `scriptTask` / `manualTask` / `businessRuleTask` / `sendTask` / `receiveTask` | 仅识别 XML 标签 `task` |
| 数据 | `dataObject` / `dataStore` / data association | 无数据语义 |
| 语义扩展 | 多实例、补偿、资源约束 | 超出当前 Petri 网 token 模型 |
| 语义扩展 | 真实时间（时钟、超时绝对时刻） | timer 仅为普通 transition，无 clock |

检测到上述元素时，`scripts/check_bpmn_compatibility.py` 会报告 **不兼容**。

---

## 语义限制（⚠️ 可转换但有近似）

| 场景 | 行为 |
| --- | --- |
| XOR / event-based 网关 | 结构上保证每次选一条路径；**不**评估 sequenceFlow 上的条件 |
| OR 网关 split | 可激活一条或多条出边（非空子集）；无 BPMN 条件时按结构近似 |
| OR 网关 join | 等待所选入边子集全部到达 token |
| message flow | 仅 gating 型消息进入 Petri 网；纯信息型消息被省略 |
| timer | 与 `intermediateCatchEvent` 相同，不含真实时间推进 |

---

## 快速检查

```bash
python scripts/check_bpmn_compatibility.py path/to/model.bpmn
python -m unittest discover -s tests -v
```

详见 [`docs/compatibility/COMPATIBILITY_VERIFICATION_REPORT.md`](compatibility/COMPATIBILITY_VERIFICATION_REPORT.md)。
