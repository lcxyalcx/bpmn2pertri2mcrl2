# BPMN 转换方法对照报告（SpringOxO vs 本地方法）

## 一、报告摘要

- 在本次选定样例（`examples/pizza_official.bpmn`）上，两种方法的转换命令均成功返回（`returncode = 0`），具备产物生成能力。
- 效率上，本地方法两步总耗时约 `0.0799s`（`bpmn2pnml_local.py` `0.0429s` + `pnml2mcrl2.py` `0.0370s`），对方小组的直接转换方法约 `0.0339s`，在单次转换速度上更快。
- 本地方法（`BPMN -> PNML -> mCRL2`）生成的 mCRL2 产物通过 `mcrl22lps` 语法校验；SpringOxO 产物未通过，错误定位于 `act` 声明中的非法标识符 `6_180`。
- 结构规模上，本地方法保留了可追溯的中间网结构（27 places / 23 transitions / 56 arcs），最终 mCRL2 为 192 行；SpringOxO 直接产出 21 行 mCRL2（5 个进程定义，8 条通信规则）。
- 命名可读性方面，本地产物动作名全部满足 mCRL2 标识符规则（23/23）；SpringOxO 为 31/32，存在 1 个非法动作名，且命名风格混合了语义名与 BPMN ID 派生名。
- 语义覆盖观察显示：两种方法均体现了并行网关、事件分支与跨参与者消息交互；但由于当前样例不含子流程（`subProcess = 0`），暂无法给出子流程转换质量的实证结论。
- LTS 图与状态空间摘要已生成，可用于报告或答辩展示：
  - `docs/verification/pizza_official/pizza_official_bounded_lts.svg`
  - `docs/verification/pizza_official/pizza_official_verification_summary.svg`
  - LTS 摘要：`200` 个状态、`199` 条迁移、`18` 个动作标签、确定性为 `yes`

## 二、对比对象与实验环境

### 2.1 对比对象

- **本地方法（本仓库）**：`BPMN -> PNML -> mCRL2`
  - 脚本链路：`bpmn2pnml_local.py`、`pnml2mcrl2.py`
- **SpringOxO 方法（外部仓库）**：`BPMN -> mCRL2`
  - 脚本：`scripts/bpmn2mcrl2.py`

### 2.2 输入模型与特征

- 本次选中输入：`examples/pizza_official.bpmn`
- 该 BPMN 的关键元素计数（摘自 `results.json`）：
  - participant: 2
  - process: 2
  - task: 9
  - eventBasedGateway: 1
  - parallelGateway: 1
  - messageFlow: 6
  - subProcess: 0

### 2.3 运行环境（结果记录口径）

- 结果根目录：`docs/comparison/springoxo_vs_local/`
- SpringOxO 代码路径（本次运行）：`/private/tmp/springoxo_bpmn2mcrl2`
- 语法校验工具：`mcrl22lps`（在本次运行中可用）

## 三、实验方法与复现命令

### 3.1 实验方法

本对照由 `docs/comparison/springoxo_vs_local/scripts/run_comparison.py` 统一执行，流程包括：

1. 按既定策略选择输入（优先 `examples/pizza_official.bpmn`，必要时回退 `examples/pizza.bpmn`）。
2. 分别执行本地链路与 SpringOxO 链路，记录命令返回码、耗时、标准输出/错误输出。
3. 对产物执行结构统计：
   - 本地 PNML：place/transition/arc/token 统计；
   - 两侧 mCRL2：行数、进程数、`allow` 动作数、`comm` 规则数、动作命名可读性统计。
4. 对两侧 mCRL2 执行 `mcrl22lps` 语法校验。

### 3.2 复现命令

```bash
python docs/comparison/springoxo_vs_local/scripts/run_comparison.py \
  --repo-root . \
  --spring-repo-root /tmp/springoxo_bpmn2mcrl2 \
  --output-json docs/comparison/springoxo_vs_local/results.json
```

## 四、结果对照

### 4.1 成功率（命令执行层）

- 本地方法：
  - `bpmn2pnml_local.py`：成功（`returncode=0`）
  - `pnml2mcrl2.py`：成功（`returncode=0`）
- SpringOxO：
  - `bpmn2mcrl2.py`：成功（`returncode=0`）
- 结论：在“文件生成/命令执行”口径下，双方本次均成功。

### 4.2 转换效率

- 本地方法：
  - `bpmn2pnml_local.py`：`0.0429s`
  - `pnml2mcrl2.py`：`0.0370s`
  - 合计：`0.0799s`
- SpringOxO：
  - `bpmn2mcrl2.py`：`0.0339s`
- 结论：对方小组的直接转换在单次生成速度上更快；本地方法虽然多一步，但保留了 PNML 中间层，后续可检查、可修正、可复用。

### 4.3 语法校验（mCRL2 可执行性）

- 本地 mCRL2：`mcrl22lps` 校验通过（`ok=true`）
- SpringOxO mCRL2：`mcrl22lps` 校验失败（`ok=false`）
  - 错误摘要：`Line 5, column 2: syntax error after 'act'`
  - 触发点：动作名 `6_180` 不符合 mCRL2 标识符规则（以数字开头）

### 4.4 结构规模

- 本地 PNML：27 places、23 transitions、56 arcs、1 个初始 token
- 本地 mCRL2：192 行、1 个进程定义、23 个动作
- SpringOxO mCRL2：21 行、5 个进程定义、32 个动作、15 个 `allow` 动作、8 条 `comm` 规则

### 4.5 命名可读性

- 本地 mCRL2：
  - 总动作数：23
  - 合法标识符：23
  - 非法标识符：0
- SpringOxO mCRL2：
  - 总动作数：32
  - 合法标识符：31
  - 非法标识符：1（`6_180`）
- 观察：本地方法动作名以业务语义动词短语为主；SpringOxO 同时包含语义动作与 BPMN ID 派生动作，后者在当前样例暴露词法风险。

### 4.6 语义覆盖观察

- **并行网关**：两侧均有建模痕迹；SpringOxO 通过 `s_start_gw_1`、`s_sync_1_0`、`s_sync_1_1` 与 `comm`/`allow` 体现并行分支与汇聚；本地方法在 Petri 网中表现为并发分支与同步变迁。
- **事件分支**：两侧均体现“等待披萨/超时催单”的行为分支（如 `event_60_minutes`、`where_is_my_pizza` 相关路径）。
- **消息流**：两侧均体现跨参与者交互；SpringOxO 显式使用 `s_`/`r_`/`c_` 三类动作及通信规则，本地方法通过消息相关 place/transition 联动实现。
- **子流程覆盖**：当前输入 `subProcess=0`，因此本次无法对“子流程转换能力”做运行期实证比较。

## 五、关键差异分析（差异成因）

1. **转换架构差异**  
   本地方法经由 PNML 中间层，具备显式网结构与命名再加工环节；SpringOxO 直接从 BPMN 输出 mCRL2，路径更短但对源命名约束更敏感。

2. **命名约束处理差异**  
   本地方法在当前产物中未出现非法动作名；SpringOxO 直接保留了以数字开头的 ID 派生标识符（`6_180`），导致语法校验失败。该差异是本次“可执行性分化”的直接原因。

3. **协作语义编码风格差异**  
   SpringOxO 采用 `comm + allow` 显式通信建模，表达紧凑且便于阅读协作同步规则；本地方法基于网状态演化，结构可追溯性更强，便于网级统计与后续结构分析。

4. **产物规模与可追溯性取舍差异**  
   本地产物更长但包含完整结构映射；SpringOxO 产物更短、抽象更高，但在当前样例下暴露了命名健壮性问题。

## 六、风险与限制

- 本次仅覆盖单一样例（`pizza_official`），不代表在复杂 BPMN（子流程、边界事件、条件网关）上的总体表现。
- 当前比较以“生成成功 + 语法可解析 + 结构统计 + 静态语义观察”为主，尚未进入“行为等价/性质保持”层面验证。
- SpringOxO 结果依赖外部仓库当前版本与本地临时副本状态；若上游变更，结果可能发生漂移。
- 子流程能力在本次输入上不可观测（`subProcess=0`），相关结论只能保持审慎表述。

## 七、改进建议与下一步计划

1. **优先修复命名合法化问题**  
   在 SpringOxO 输出阶段增加动作名规范化策略（如对数字开头标识符自动前缀化），先恢复 mCRL2 语法可执行性。

2. **扩展样例矩阵并批量对比**  
   新增含子流程、边界事件、排他网关、多消息回路的样例，形成批量结果并统计通过率分布。

3. **补充行为层验证**  
   在两侧均可通过 `mcrl22lps` 后，继续进行 LPS/LTS 规模、死锁检查与关键性质（模态公式）验证，提升结论说服力。

4. **统一评价口径与自动化产出**  
   将“语法通过率、命名合法率、结构规模、关键语义覆盖项”固定为对照模板，持续输出可直接用于周报/组会的标准报告。
