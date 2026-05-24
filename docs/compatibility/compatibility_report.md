# BPMN 转换兼容性报告

检查范围：本地 `bpmn2pnml_local.py` + `pnml2mcrl2.py` 流水线。

## 支持矩阵

| BPMN 元素 | 状态 |
| --- | --- |
| `boundaryEvent` | 支持 |
| `callActivity` | 支持 |
| `complexGateway` | 支持 |
| `endEvent` | 支持 |
| `eventBasedGateway` | 支持 |
| `exclusiveGateway` | 支持 |
| `inclusiveGateway` | 支持 |
| `intermediateCatchEvent` | 支持 |
| `intermediateThrowEvent` | 支持 |
| `parallelGateway` | 支持 |
| `startEvent` | 支持 |
| `task` | 支持 |
| `messageFlow` | 支持 |
| `sequenceFlow` | 支持 |
| `choreographyTask` | 不支持（编排任务未建模） |
| `conversation` | 不支持（会话未建模） |
| `globalChoreographyTask` | 不支持（编排任务未建模） |
| `globalTask` | 不支持（全局任务未建模） |

## 检查结果

### `examples/pizza.bpmn` — 兼容

- 解析节点：4
- sequence flow：3
- message flow：0
- PNML：5 places / 4 transitions / 8 arcs
- mCRL2 已生成：true
- mCRL2 语法验证：True
- bounded mCRL2 语法验证：True

| 元素 | 数量 | 状态 | 说明 |
| --- | ---: | --- | --- |
| `endEvent` | 1 | supported |  |
| `sequenceFlow` | 3 | supported |  |
| `startEvent` | 1 | supported |  |
| `task` | 2 | supported |  |

### `examples/pizza_official.bpmn` — 兼容

- 解析节点：18
- sequence flow：18
- message flow：6
- PNML：27 places / 23 transitions / 56 arcs
- mCRL2 已生成：true
- mCRL2 语法验证：True
- bounded mCRL2 语法验证：True

| 元素 | 数量 | 状态 | 说明 |
| --- | ---: | --- | --- |
| `endEvent` | 2 | supported |  |
| `eventBasedGateway` | 1 | supported |  |
| `intermediateCatchEvent` | 3 | supported |  |
| `messageFlow` | 6 | supported |  |
| `parallelGateway` | 1 | supported |  |
| `sequenceFlow` | 18 | supported |  |
| `startEvent` | 2 | supported |  |
| `task` | 9 | supported |  |

