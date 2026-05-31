# BPMN 转换阶段总结

日期：2026-05-31

## 这周做了什么

- 优化了本地链路 `BPMN -> PNML -> mCRL2`
  - `bpmn2pnml_local.py`：给 `sequenceFlow` 和 `messageFlow` 加了索引缓存，减少重复扫描
  - `pnml2mcrl2.py`：把“全 place 链式更新”改成“只对变化的 place 生成分支”，减少 mCRL2 冗余
- 补充了验证流程，可以生成 `LPS / LTS / SVG / results.json`
- 用官方 Pizza 样例做了本地方法和网页方法的对比

## Pizza 实例对比

统一输入是官方 Pizza BPMN，比较的是两组方法：

- 本地方法：`BPMN -> bpmn2pnml_local.py -> PNML -> pnml2mcrl2.py -> mCRL2`
- 网页方法：`BPMN -> bpmn2petrinet.com -> PNML -> pnml2mcrl2.py -> mCRL2`

这里的“网页方法”指的是 `bpmn2petrinet.com` 这个在线 BPMN 转 Petri net 工具，本项目通过 `bpmn2mcrl2_web.py` 调用它先导出 PNML，再继续转成 mCRL2。

为了让两边可以直接对照，我把比较口径统一成了：

- 同一份官方 Pizza 输入
- 同一套 bounded 设置：每个 place 最多 1 个 token，LTS 最多看前 200 个状态
- 同一组可观察行为：下单、送达、收款、安抚顾客、联合结束

### 本地方法

- 路线更细，保留更完整的 Petri net 结构
- 总耗时：`0.0799s`
  - `bpmn2pnml_local.py`：`0.0429s`
  - `pnml2mcrl2.py`：`0.0370s`
- 结果：`mcrl22lps` 通过
- PNML 规模：`27 places / 23 transitions / 56 arcs`

### 网页方法

- 路线更短，生成速度更快
- 结果：`mcrl22lps` 通过
- PNML 规模：`24 places / 18 transitions / 46 arcs`
- 在 Pizza 里会把部分 message flow 和 timer 约束压缩得更紧，导致状态空间更小

### 对比结论

- 网页方法更快、模型更紧凑
- 本地方法多一步，但语义更完整，也更方便检查和修正
- 对课程项目来说，本地方法更适合做主线，网页方法适合做对照
- 这里的“对齐”不是要求两边状态数一样，而是要求它们在同一输入和同一边界条件下比较，因此 LTS 图可以作为有效对照，但不能只拿状态数本身判断优劣

## LTS 图

### 本地方法的 LTS

![Local LTS](/Users/jacobliu/Downloads/bpmn2pertri2mcrl2-main/docs/runs/pizza_official_redownload_20260518/pizza_official_downloaded_bounded_lts.svg)

摘要：

- 状态数：200
- 迁移数：199
- 动作标签数：18
- 确定性：是

### 网页方法的 LTS

![Web LTS](/Users/jacobliu/Downloads/bpmn2pertri2mcrl2-main/docs/runs/pizza_official_redownload_20260518/pizza_official_web_bounded_lts.svg)

摘要：

- 状态数：54
- 迁移数：53
- 动作标签数：10
- 确定性：是

## 简短结论

- 前两张 LTS 是同一 Pizza 输入、同一 bounded 口径下的对比图，可以直接比较
- 本地方法的状态数更大，说明它保留了更多可观察行为
- 网页方法的状态数更小，说明它把部分语义压缩掉了
- 所以本地方法更稳，网页方法更快

## 为什么会有这种差异

两组结果差异主要来自三件事：

1. **中间层是否保留**
   - 本地方法保留 PNML，所以多了一层语义检查点，模型更大，但更容易修正
   - 网页方法也经过 PNML，但它是黑盒通用映射，保留的协作语义更少
   - 本次对比中不涉及直出方法，核心比较仍然是“保留更多语义的本地方法”与“更紧凑的网页方法”

2. **BPMN 语义怎么编码**
   - 本地方法对 message flow、event-based gateway、timer 做了 BPMN-aware 处理
   - 网页方法更偏通用 Petri 网转换，Pizza 上会把一些依赖压得过紧
3. **命名合法性和工程健壮性**
   - 本地方法的动作名都符合 mCRL2 语法
   - 网页方法在本次 Pizza 样例上也通过了语法检查

## 可引用文件

- 本地 mCRL2：`examples/pizza_official_local.mcrl2`
- 本地 LTS 图：`docs/runs/pizza_official_redownload_20260518/pizza_official_downloaded_bounded_lts.svg`
- 网页 mCRL2：`docs/runs/pizza_official_redownload_20260518/pizza_official_web.mcrl2`
- 网页 LTS 图：`docs/runs/pizza_official_redownload_20260518/pizza_official_web_bounded_lts.svg`
- 对比说明：`docs/runs/pizza_official_redownload_20260518/PIZZA_LOCAL_VS_WEB_COMPARISON.md`
