# bpmn2pertri2mcrl2 周进展汇报（2026-05-24 ~ 2026-05-29）

## 1. 本周目标

- 提升大规模 BPMN/PNML 模型的转换效率与生成结果可维护性。
- 将验证流程从专项脚本升级为可复用的通用工作流。
- 完成官方 Pizza 示例的可复现验证产物打包，支撑汇报与复核。

## 2. 本周完成情况

### 2.1 转换性能与模型生成优化

- 优化 `bpmn2pnml_local.py` 的流连接处理逻辑：
  - 为 `sequenceFlow` 和 `messageFlow` 增加入/出索引缓存。
  - 减少节点遍历时的重复全量扫描，降低大模型转换开销。
- 优化 `pnml2mcrl2.py` 的状态更新表达式生成：
  - 由“全 place 链式 if”改为“仅对发生变化的 place 生成分支”。
  - 缩短 `update_t_*` 公式长度，提高生成模型可读性与求解友好性。

### 2.2 通用验证工作流建设

- 新增 `scripts/verify_workflow.py`：
  - 统一支持输入类型：`.bpmn` / `.pnml` / `.mcrl2`。
  - 自动执行 `mCRL2 -> LPS -> LTS`，并导出 `AUT / DOT / SVG`。
  - 支持加载 `.mcf` 执行 PBES 求解，输出 `results.json` 与报告文档。
- 新增 `scripts/verification_utils.py`：
  - 抽取 LTS 解析、布尔结果解析、LTS SVG 生成等公共能力。
  - 增加 `resolve_tool`，支持从 PATH 与本地 `.tools` 双路径解析工具，提升环境兼容性。
- 增强公式求解后端策略：
  - 在通用验证脚本中支持 `--formula-backend auto|lps|lts`。
  - 默认自动回退机制可在不同工具链状态下提高成功率。

### 2.3 官方 Pizza 验证结果打包

- 更新 `scripts/check_pizza_official.py` 与 `scripts/rerun_pizza_official_pipeline.py`：
  - 对齐共享工具能力，减少重复实现。
  - 输出结果结构化并写入 `docs/verification/pizza_official`。
- 完整沉淀官方示例验证资产：
  - 主模型与中间产物：`*.mcrl2`, `*.lps`, `*.lts`, `*.dot`, `*.aut`。
  - 可视化与摘要：`*_lts.svg`, `*_verification_summary.svg`, `results.json`。
  - 见证轨迹：`*_witness.lts`（覆盖关键可达性与死锁检查）。

### 2.4 测试与文档

- 扩展 `tests/test_converter.py`：
  - 增加大规模网络（1200 places）下更新表达式稀疏化测试。
- 新增 `tests/test_verification_workflow.py`：
  - 覆盖公式收集、工具链 mock 执行、报告产物生成等路径。
- 更新 `README.md`、`docs/PROJECT_SUMMARY.md`、`docs/compatibility/COMPATIBILITY_VERIFICATION_REPORT.md`，补充通用验证入口与术语对齐。

### 2.5 方法对比与外部项目调研

- 调研并整理了另一个小组的 **BPMN -> mCRL2** 项目（SpringOxO）作为对照基线，重点比较其与本地主线 `BPMN -> PNML -> mCRL2` 的实现方式、输出规模和语义保真度。
- 以官方 Pizza 流程为统一样例，完成了两条路线的初步对照：
  - 本地方法分两步完成：`BPMN -> PNML` 再 `PNML -> mCRL2`，保留中间 Petri 网结构，便于检查、修正和复用；
  - 对方小组的方法是直接 `BPMN -> mCRL2`，路径更短，但对 BPMN 命名、协作语义编码和输出合法性更敏感。
- 初步效率结果（同一 Pizza 样例）：
  - 本地方法：`bpmn2pnml_local.py` 约 `0.0429s`，`pnml2mcrl2.py` 约 `0.0370s`，两步合计约 `0.0799s`
  - 对方小组方法：`bpmn2mcrl2.py` 约 `0.0339s`
  - 说明：直接转换在“生成速度”上更快，但本地方法额外保留了可检查的 PNML 中间层，便于后续验证与修正。
- 已将对照实验结果整理到 `docs/comparison/springoxo_vs_local/`，其中包含效率统计、mCRL2 可执行性检查，以及可直接插入报告的对比图。

### 2.6 LTS Graph 与验证可视化

- 在验证链路中补充了 LTS Graph / 状态空间可视化输出，用于展示模型的可达状态、分支结构和终止行为。
- 关键产物包括：
  - `docs/verification/pizza_official/pizza_official_bounded_lts.svg`
  - `docs/verification/pizza_official/pizza_official_verification_summary.svg`
- 这些图可以直接放入报告或答辩 PPT，作为“转换后模型确实可执行且可验证”的证据。
- 其中 LTS 摘要结果显示：`200` 个状态、`199` 条迁移、`18` 个动作标签，且状态空间为确定性，适合用作方法对比的可视化证据。

### 2.7 基准样例覆盖扩展（已完成补充）

- 新增基准样例目录 `examples/benchmarks/`，扩展至 11 个组合场景：
  - 跨网关组合：`gateway_xor_parallel_mix.bpmn`（XOR + AND 混合控制流）。
  - 跨网关扩展：`gateway_xor_or_mix.bpmn`（XOR + OR 混合控制流）。
  - 事件并行组合：`eventbased_parallel_mix.bpmn`（eventBasedGateway + parallelGateway）。
  - 消息交互组合：`message_boundary_callactivity.bpmn`（messageFlow + boundaryEvent + callActivity/userTask）。
  - 跨池消息循环：`cross_pool_message_loop.bpmn`（双流程反馈/更新回路）。
  - 边界并行升级：`boundary_parallel_escalation.bpmn`（boundaryEvent + parallel escalation）。
  - 子流程组合：`subprocess_transaction_nested.bpmn`（subProcess + transaction + nested subProcess）。
  - 嵌套容器消息组合：`nested_container_message_combo.bpmn`（nested container + message dispatch）。
  - 多实例近似语义：`multi_instance_approximation.bpmn`（multiInstanceLoopCharacteristics 近似处理）。
  - 边界中断模式：`boundary_interrupt_modes.bpmn`（interrupting/non-interrupting boundary event 组合）。
  - 多协作方编排：`multi_collab_message_orchestration.bpmn`（三方消息编排）。
- 新增清单 `examples/benchmarks/suite_manifest.json`，统一维护样例类别、目标与覆盖标签。
- 新增批量检查脚本 `scripts/run_benchmark_suite.py`，可一键执行样例兼容性验证并输出报告。
- 执行结果（2026-05-31）：11/11 样例兼容，生成报告：
  - `docs/compatibility/benchmarks/benchmark_suite_report.json`
  - `docs/compatibility/benchmarks/benchmark_suite_report.md`

## 3. 本周关键成果（可量化）

- 5 月 29 日当日完成 3 次关键提交，形成连续交付链路：
  - 性能优化：`deca733a`（Optimize large-model conversion paths）
  - 通用验证：`f95948c8`（Add generic verification workflow）
  - 结果打包：`11e027cf`（Bundle verification workflow and official results）
- 官方 Pizza 验证资产已可直接复用，支持复现、审阅和演示。
- 转换脚本与验证脚本的模块化程度提升，后续扩展新样例成本下降。
- 基准样例覆盖从单一 Pizza 扩展至 11 个高频组合场景，当前覆盖结果为 11/11 通过。

## 4. 风险与待改进点

- 当前验证主流程中，部分场景仍以 witness/reachability/deadlock 作为执行后端，PBES 在复杂公式上的一致性仍需持续回归验证。
- 多实例、复杂子流程深层语义仍存在近似处理空间，后续需补充更高保真语义映射策略。
- 需进一步扩大基准样例集，避免仅在 Pizza 类流程上表现优秀。

## 5. 下周计划

- 基准样例扩展第四阶段：继续补充补偿事件、错误事件与更复杂跨池协同闭环场景。
- 补齐可复用 `.mcf` 性质库，推动“模型 + 性质 + 结果”标准化沉淀。
- 继续收敛统一 CLI，支持批处理验证与自动化报告导出。
- 针对复杂流程开展性能压测，形成转换与验证耗时基线。

## 6. 需要协同支持（可选）

- 若用于正式答辩/周会展示，建议统一一套“示例输入 + 命令 + 结果文件”的演示模板，降低现场环境差异风险。
- 如需对外公开结果，建议补充版本标签与结果快照（含工具版本、命令行参数、生成时间）。

---

文档生成时间：2026-05-31  
适用场景：组会周报 / 导师汇报 / 阶段性里程碑记录
