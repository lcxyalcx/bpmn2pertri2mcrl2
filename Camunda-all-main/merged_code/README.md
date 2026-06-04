# 集装箱出口跨组织协作流程（Camunda 8 / Zeebe）

> 并发理论大作业「跨组织协作业务流程系统的行为分析与优化」工程实现。

## 架构

9 个组织 + 1 个 Zeebe 引擎中心。当前合并 BPMN 中有 25 条 kebab-case message flow 和 29 个 Zeebe task type，关联键统一为 `orderId`。

| 组织 | 缩写 | 角色 |
|---|---|---|
| Owner | OWN | 货主 — 流程发起方 |
| Freight Forwarder | FFW | 货代 — 枢纽协调者 |
| Shipping Agency | SAG | 船代 — 船舶/舱位/舱单 |
| Customs Broker | CUB | 报关行 |
| Customs | CUS | 海关 — 监管放行 |
| SBGS | SBG | 边防 — 船员查验 |
| Container Terminal | CTE | 码头 — 装卸枢纽 |
| Transport | TRP | 车队 — 集装箱陆运 |
| Depot | DPT | 货场 — 空箱存放 |

业务模型在 [`bpmn/all.bpmn`](bpmn/all.bpmn) 中（包含 9 个 participant、9 个 process、25 条 message flow、8 个 parallel gateway）。

## 目录结构

```
.
├── bpmn/all.bpmn          # 唯一权威 BPMN（合并 9 个 participant）
├── shared/                # 跨组共享：消息常量、task type、Zeebe 客户端、工具
├── workers/<org>/index.ts # 9 个组织的 Job Worker（每组一个文件）
├── scripts/
│   ├── deploy.ts          # 部署 BPMN
│   └── start-all.ts       # 并行启动 9 个 worker
├── docs/                  # 大作业命名规则 PDF、消息契约、整合需求文档
└── _archive/C1..C5/       # 原始小组代码（不再使用，保留用于回溯）
```

## 环境要求

- Node.js ≥ 18（建议 v20 LTS）
- Camunda 8 Run（已安装在 `E:\camunda`）

## 步骤 1：启动 Camunda 8 Run

```powershell
cd E:\camunda
.\c8run.exe start
# 或 .\start.bat —— 视你的 c8run 版本而定
```

等待启动完成，确认以下服务可访问：

| 服务 | 默认地址 | 用途 |
|---|---|---|
| Zeebe gRPC | `localhost:26500` | gRPC API |
| Zeebe REST | `http://localhost:8088` | REST API（本仓库 SDK 使用） |
| Operate | `http://localhost:8081` | 流程实例监控（demo / demo） |
| Tasklist | `http://localhost:8082` | 用户任务（本项目无 user task） |

> ⚠️ 若你的 c8run 端口不同，编辑 `.env` 中的 `ZEEBE_REST_ADDRESS`、`ZEEBE_ADDRESS`。

## 步骤 2：安装依赖与配置

```powershell
cd D:\vue_workspace\Camunda-all-test
npm install
copy .env.example .env
# 按需修改 .env 中的端口
```

## 步骤 3：部署 BPMN

```powershell
npm run deploy
```

成功输出形如：
```
Deployment succeeded:
  - bpmnProcessId=Process_1n9bswo   version=1  key=...
  - bpmnProcessId=Process_FF        version=1  key=...
  - bpmnProcessId=Process_SA        version=1  key=...
  - bpmnProcessId=Process_SBGS      version=1  key=...
  - bpmnProcessId=Process_CB        version=1  key=...
  - bpmnProcessId=Process_Customs   version=1  key=...
  - bpmnProcessId=Process_CT        version=1  key=...
  - bpmnProcessId=Process_Transport version=1  key=...
  - bpmnProcessId=Process_Depot     version=1  key=...
```

## 步骤 4：启动全部 Worker

```powershell
npm run start:all
```

成功输出形如：
```
Starting all 9 organization workers...
  Zeebe REST: http://localhost:8088
  Zeebe gRPC: localhost:26500

[OWN] workers registered: fill-certificate, handle-order, order-to-ffw, outbound-ctn-to-transport, payment
[FFW] workers registered: so-to-sa, order-info-to-cb, equipment-receipt-to-transport
[SAG] workers registered: handle-manifest, sa-equipment-receipt-received, ask-for-ctn, ship-arrive-at-ct, crewlist-received, expense-note-received
[CUB] workers registered: declaration-submitted, inspection-appointment
[CUS] workers registered: ciq, inspection, clearance-to-broker, customs-clearance-to-terminal
[SBG] workers registered: personnel-info-registration
[CTE] workers registered: load-ctn, arrival-to-customs, ship-departure-notification
[TRP] workers registered: ctn-to-owner, outbound-ctn-to-depot
[DPT] workers registered: empty-ctn-to-transport, ctn-arrival-info-to-sa, outbound-ctn-to-ct

✅ All 9 worker groups registered. Waiting for jobs...
```

> 如果你只想启动某一个组织调试，可执行 `npm run start:owner`（或 `start:ffw / start:sag / start:cub / start:cus / start:sbg / start:cte / start:trp / start:dpt`）。

---

## 步骤 5：在 Camunda Modeler 中发起流程并验证

### 5.1 打开 Camunda Modeler

1. 启动 **Camunda Modeler**（你截图里的 5.45.0 即可）
2. `File → Open File...`，选择 `D:\vue_workspace\Camunda-all-test\bpmn\all.bpmn`
3. 模型加载后，左下应能看到 `c8run (local)` 标志为绿色（与本地 Camunda 8 已连接）

### 5.2 启动 Owner 流程实例（货主下单）

`all.bpmn` 是 **collaboration**，包含 9 个独立 process。Modeler 只能挑其中一个作为入口启动。Owner 是入口：

1. 选中 **Owner**（货主泳道）里的 **空白处** 或 start event `Event_0n197sl`
2. 右下点击橙色 **Start instance**（小三角图标），或菜单 `Run → Run process`
3. 弹出的 Variables 对话框里填：

   ```json
   {
     "orderId": "ORDER-20260527-001"
   }
   ```

4. 在 Process 下拉中确保选中 `Process_1n9bswo`（Owner 的进程 id，名 "all"）
5. 点击 **Start**

### 5.3 用同一个 orderId 启动 Customs、Container Terminal 与 Transport 流程

由于本作业把 9 个 process 拆开了，且其中 **Owner**（Process_1n9bswo）、**Customs**（Process_Customs）、**Container Terminal**（Process_CT）和 **Transport**（Process_Transport）的 start event 是普通 startEvent 而非 message start event，它们不会被消息自动唤醒。可用脚本一次性启动这 4 个入口流程：

```powershell
npm run start:processes ORDER-20260527-001
```

如果在 Modeler 中手动启动，重复 5.2 的操作，依次为：

- `Process_Customs` —— Variables 同样填 `{ "orderId": "ORDER-20260527-001" }`
- `Process_CT` —— Variables 同样填 `{ "orderId": "ORDER-20260527-001" }`
- `Process_Transport` —— Variables 同样填 `{ "orderId": "ORDER-20260527-001" }`

> 其余 5 个 process（FF / SA / SBGS / CB / Depot）的 start event 是 **Message Start Event**，会被上游的 publishMessage 自动唤醒，无需手动启动。

### 5.4 在 Camunda Operate 中观察

打开 `http://localhost:8081`，账号 `demo` / `demo`：

1. 左侧 **Processes** 列出 9 个流程定义
2. 切到 **Process Instances**，按 `orderId=ORDER-20260527-001` 过滤
3. 预期看到 **9 个实例** 从 `Active` 走向 `Completed`，无 incident、无卡死
4. 同时 `npm run start:all` 终端会持续打印 task 执行日志，形如：
   ```
   [2026-05-27T...] [OWN/handle-order] orderId=ORDER-20260527-001
   [2026-05-27T...] [OWN/order-to-ffw] orderId=ORDER-20260527-001
   [2026-05-27T...] [FFW/so-to-sa] orderId=ORDER-20260527-001
   ...
   ```

---

## 常见问题

### Q1：deploy 报 ECONNREFUSED
- 没启动 Camunda 8 Run；确认 `E:\camunda\c8run.exe` 已运行
- 端口不对；检查 `.env` 的 `ZEEBE_REST_ADDRESS`（c8run 默认 8088，旧版可能是 8080）

### Q2：worker 报 `No worker found for task type 'xxx'`
- 这是 Zeebe 在告诉你某个 task 一直没人接 —— 检查 [shared/task-types.ts](shared/task-types.ts) 中是否有这个 type，对应 worker 文件是否注册了

### Q3：流程卡在某个 Catch Event 不动
- 进 Operate 的 Process Instance 详情，点 catch event 看它等的 message 名是什么
- 对照 [shared/messages.ts](shared/messages.ts) 检查 publishMessage 的 `name` 是否完全匹配，`correlationKey` 是否就是 `orderId`
- 也可以在终端 grep worker 输出，看 publish 是否真的执行过

### Q4：多个流程实例都在跑（之前测试残留）
- Operate 上勾选旧实例 → Cancel
- 或者改用一个新的 orderId 再跑一遍

### Q5：流程跑通了但 9 个实例不是全部 Completed
- 通常是某个 Catch Event 没收到对应 publish。回到 Q3 思路排查
- 也可能是某个并行分支的某条消息没发（比如 SA 的 handle-manifest 要给 FF + CT + Customs 三家同时发，缺一就卡）

---
