# Pizza 官方样例重新转换报告

本次运行直接从官方页面重新下载 Pizza BPMN 样例，再在本地重新执行：

`BPMN -> PNML -> mCRL2 -> bounded LTS`

## 官方来源

- 页面：[https://maude.lcc.uma.es/BPMN-R/pizza/](https://maude.lcc.uma.es/BPMN-R/pizza/)
- 原始 BPMN：[https://maude.lcc.uma.es/BPMN-R/pizza/files/triso%20-%20Order%20Process%20for%20Pizza%20V4.bpmn](https://maude.lcc.uma.es/BPMN-R/pizza/files/triso%20-%20Order%20Process%20for%20Pizza%20V4.bpmn)
- 带注释 BPMN：[https://maude.lcc.uma.es/BPMN-R/pizza/files/pizza-with-comments.bpmn](https://maude.lcc.uma.es/BPMN-R/pizza/files/pizza-with-comments.bpmn)

## 本次运行产物

- BPMN：`docs/runs/pizza_official_redownload_20260518/pizza_official_downloaded.bpmn`
- 带注释 BPMN：`docs/runs/pizza_official_redownload_20260518/pizza_official_with_comments_downloaded.bpmn`
- 官方示意图：`docs/runs/pizza_official_redownload_20260518/pizza_official_source.png`
- PNML：`docs/runs/pizza_official_redownload_20260518/pizza_official_downloaded_local.pnml`
- mCRL2：`docs/runs/pizza_official_redownload_20260518/pizza_official_downloaded_local.mcrl2`
- bounded mCRL2：`docs/runs/pizza_official_redownload_20260518/pizza_official_downloaded_bounded.mcrl2`
- LPS：`docs/runs/pizza_official_redownload_20260518/pizza_official_downloaded_bounded.lps`
- LTS：`docs/runs/pizza_official_redownload_20260518/pizza_official_downloaded_bounded.lts`
- AUT：`docs/runs/pizza_official_redownload_20260518/pizza_official_downloaded_bounded.aut`

## 统计

- BPMN：2 个 process，18 个 flow node，6 条 message flow
- PNML：27 个 place，23 个 transition，56 条 arc
- mCRL2：27 个 place alias，23 个 action
- bounded LTS：200 个状态，199 条迁移

## 可视化

### 1. 流程总览

![pipeline](docs/runs/pizza_official_redownload_20260518/01_pipeline.svg)

### 2. 官方 BPMN 输入概览

![bpmn-summary](docs/runs/pizza_official_redownload_20260518/02_bpmn_summary.svg)

### 3. 官方页面中的 BPMN 图

![bpmn-image](docs/runs/pizza_official_redownload_20260518/pizza_official_source.png)

### 4. PNML 结构概览

![pnml-overview](docs/runs/pizza_official_redownload_20260518/03_pnml_overview.svg)

### 5. mCRL2 结构概览

![mcrl2-overview](docs/runs/pizza_official_redownload_20260518/04_mcrl2_summary.svg)

### 6. bounded LTS 可视化

![lts-overview](docs/runs/pizza_official_redownload_20260518/pizza_official_downloaded_bounded_lts.svg)
