# SpringOxO vs 本地方法：BPMN 转换效果对比

本目录对比了两种 BPMN 到 mCRL2 的方法在同一输入上的转换效果：

- 本仓库本地方法：`BPMN -> PNML -> mCRL2`
- SpringOxO 方法：`BPMN -> mCRL2`（仓库：<https://github.com/SpringOxO/bpmn2mcrl2>）

结构化实验结果见 `results.json`，可重复执行脚本见 `scripts/run_comparison.py`。
正式对照报告见 `COMPARISON_REPORT.md`（用于导师/组会汇报口径）。

## 对比输入与选择策略

- 优先输入：`examples/pizza_official.bpmn`
- 回退输入：`examples/pizza.bpmn`（仅当前者无法同时跑通两种方法时启用）
- 本次实际输入：`examples/pizza_official.bpmn`

该输入包含：2 个 participant、2 个 process、9 个 task、1 个 event-based gateway、1 个 parallel gateway、6 条 message flow。

## 复现方式

1. 下载 SpringOxO 代码到临时目录（避免污染仓库根目录）：

```bash
curl -L --fail --output /tmp/springoxo_bpmn2mcrl2.zip https://codeload.github.com/SpringOxO/bpmn2mcrl2/zip/refs/heads/main
rm -rf /tmp/springoxo_bpmn2mcrl2
mkdir -p /tmp/springoxo_bpmn2mcrl2
bsdtar -xf /tmp/springoxo_bpmn2mcrl2.zip -C /tmp/springoxo_bpmn2mcrl2 --strip-components 1
```

2. 一键执行对比（含两种转换、统计、mCRL2 语法验证）：

```bash
python docs/comparison/springoxo_vs_local/scripts/run_comparison.py \
  --repo-root . \
  --spring-repo-root /tmp/springoxo_bpmn2mcrl2 \
  --output-json docs/comparison/springoxo_vs_local/results.json
```

## 实验结论（摘要）

- 两种方法都能完成“文件生成”层面的转换（命令返回码为 0）。
- 本地方法产物可被 `mcrl22lps` 成功解析；SpringOxO 产物在 `act` 声明处出现非法动作名 `6_180`，语法校验失败。
- 本地方法保留了完整 PNML 中间网结构（27 places / 23 transitions / 56 arcs），可追溯且便于网级分析；SpringOxO 直接生成 mCRL2，产物更短但缺少 PNML 中间工件。
- message flow 建模风格差异明显：本地方法通过 PNML 中消息 place 与变迁联动；SpringOxO 使用 `s_/r_/c_` 动作和 `comm+allow` 显式握手。
- 语义保真方面，本次输入覆盖并行网关、事件网关、消息流；子流程在该输入中数量为 0，因此无法做“基于运行产物”的子流程实证比较，只能做静态能力声明比较。
- 运行复杂度方面，本地方法分两步但结果稳定；SpringOxO步骤更短，但当前样例下输出可执行性受动作命名规则影响。

## 关键观察（基于 `results.json`）

- 成功性：
  - 本地：`bpmn2pnml_local.py` + `pnml2mcrl2.py` 均成功，`mcrl22lps` 通过。
  - SpringOxO：`bpmn2mcrl2.py` 成功产出文件，但 `mcrl22lps` 失败。
- 规模/结构：
  - 本地 PNML：27 places、23 transitions、56 arcs、1 个初始 token。
  - 本地 mCRL2：192 行，23 个动作，全部是合法 mCRL2 标识符。
  - SpringOxO mCRL2：21 行，32 个动作，1 个非法标识符（`6_180`），含 8 条 `comm` 同步规则。
- 可读性：
  - 本地动作多为业务语义命名（例如 `order_a_pizza`、`receive_payment`）。
  - SpringOxO动作中混有语义名与 BPMN id 派生命名，且 id 派生可能违反 mCRL2 词法约束。
- 语义保真相关：
  - 并行网关：两者都建模了分支/同步；SpringOxO显式使用 `s_start_gw_1` 与 `s_sync_1_x` 通信动作。
  - 消息流：两者都体现了跨参与者同步；SpringOxO通过 `s_/r_/c_` 三元通信规则表达，结构更显式。
  - 子流程：本输入无子流程，无法基于该输入给出行为等价性结论。

## 限制与后续建议

- 本次仅对单一输入（官方 pizza 协作样例）做实测；建议在含子流程、边界事件、条件网关的样例上扩展批量对比。
- SpringOxO 输出语法失败是当前样例暴露的阻塞点；可后续增加动作名标准化修复（例如前缀化数字开头标识符）后再做行为层验证。
- 若需要“语义等价”级别结论，建议在两者可通过 `mcrl22lps` 后，继续跑 LTS 规模、死锁与关键性质（modal formula）对比。
