# 📌 项目进展汇报（bpmn2pertri2mcrl2）

日期：2026-05-24

## ✅ 已完成工作

- **PNML → mCRL2**：`pnml2mcrl2.py`
- **BPMN → PNML → mCRL2（本地）**：`bpmn2pnml_local.py` + `pnml2mcrl2.py`
- **BPMN → PNML → mCRL2（网页）**：`bpmn2mcrl2_web.py`（bpmn2petrinet.com + Playwright）
- **官方 Pizza 完整示例**贯通：BPMN → PNML → mCRL2 → bounded LTS → 性质验证
- **BPMN 元素扩展**：
  - 全部常见网关（parallel / event-based / XOR / OR / complex）
  - `intermediateThrowEvent`、`boundaryEvent`
  - 专用任务类型（`userTask` 等）与 `callActivity`
  - 子流程容器展开（`subProcess` / `transaction` 等）
- **兼容性验证工具链**：`scripts/check_bpmn_compatibility.py`
- **文档**：`docs/BPMN_SUPPORT.md`、`docs/compatibility/COMPATIBILITY_VERIFICATION_REPORT.md`
- **单元测试**：13 项（`tests/test_converter.py`）

## 🧪 验证情况

- 单元测试：13/13 通过
- 兼容性扫描：仓库内 4 个 BPMN 样例 4/4 兼容
- 官方 Pizza：6/6 性质检查符合预期

## 📂 核心文件

| 文件 | 说明 |
| --- | --- |
| `bpmn2pnml_local.py` | 本地 BPMN-aware → PNML |
| `pnml2mcrl2.py` | PNML → mCRL2 |
| `bpmn2mcrl2_web.py` | 网页自动化转换 |
| `scripts/check_bpmn_compatibility.py` | 兼容性扫描 |
| `scripts/check_pizza_official.py` | Pizza 性质验证 |
| `docs/BPMN_SUPPORT.md` | 元素支持清单 |

## 🔜 下一步建议

- 更多 BPMN 基准样例与 PBES 级性质验证
- 多实例语义、嵌套子流程层次保留
- 统一 CLI（`convert.py --verify --visualize`）

## ⚠️ 注意事项

- 网页路径需 `python -m playwright install`
- 网关条件表达式、真实时间、补偿等仍按结构近似或不支持
- 详见 [`docs/BPMN_SUPPORT.md`](docs/BPMN_SUPPORT.md)
