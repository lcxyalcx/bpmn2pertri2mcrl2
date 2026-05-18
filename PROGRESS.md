# 📌 项目进展汇报（bpmn2pertri2mcrl2）

日期：2026-05-08

## ✅ 已完成工作

- 完成 **PNML → mCRL2** 转换脚本：`pnml2mcrl2.py`
- 完成 **BPMN → PNML → mCRL2** 端到端脚本：`bpmn2mcrl2_web.py`
  - 使用 Playwright 在浏览器上下文调用 bpmn2petrinet.com 的转换模块
  - 不依赖 UI 点击，稳定输出 PNML 并转成 mCRL2
- 加入 **Pizza 示例**：
  - `examples/pizza.bpmn`（BPMN）
  - `examples/pizza.pnml`（PNML）
  - `examples/pizza_web.mcrl2`（端到端输出）
- 编写最小测试：`tests/test_converter.py`
- 完善 README：
  - 转换原理、使用方式、流程可视化（Mermaid + Graphviz）
  - Pizza 示例完整流程说明

## 🧪 验证情况

- 单元测试：通过（`python -m unittest discover -s tests`）
- 端到端测试：Pizza 示例 BPMN → mCRL2 成功

## 📂 当前目录结构（核心）

- `pnml2mcrl2.py`：PNML → mCRL2
- `bpmn2mcrl2_web.py`：BPMN → PNML → mCRL2（网页模块）
- `examples/pizza.bpmn` / `examples/pizza.pnml`
- `examples/pizza_web.mcrl2`
- `tests/test_converter.py`
- `README.md`
- `requirements.txt`

## 🔜 下一步建议

- 接入更多 BPMN 示例（并行/分支/循环等）
- 增强 PNML 解析健壮性（多权重 arc、多个初始标记）
- 输出可选的中间 PNML 文件（用于调试）

## ⚠️ 注意事项

- `bpmn2mcrl2_web.py` 依赖 Playwright 浏览器组件（需执行 `python -m playwright install`）
- 输出 mCRL2 基于无权重 Petri Net 的 token 流动语义
