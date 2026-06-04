#!/usr/bin/env python3
"""Check BPMN compatibility with the local bpmn2pnml_local + pnml2mcrl2 pipeline."""

from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bpmn2pnml_local import (  # noqa: E402
    CONTAINER_TAGS,
    FLOW_NODE_TAGS,
    FLOW_NODE_XML_TAGS,
    TASK_TAGS,
    convert_bpmn_to_pn,
    parse_bpmn,
)
from pnml2mcrl2 import convert_file as convert_pnml_to_mcrl2, parse_pnml  # noqa: E402
from scripts.verification_utils import resolve_tool  # noqa: E402

SUPPORTED_FLOWS = {"sequenceFlow", "messageFlow"}

UNSUPPORTED_FLOW_NODES: dict[str, str] = {
    "globalTask": "全局任务未建模",
    "globalChoreographyTask": "编排任务未建模",
    "choreographyTask": "编排任务未建模",
    "conversation": "会话未建模",
}

UNSUPPORTED_WITH_WARNING: dict[str, str] = {
    "multiInstanceLoopCharacteristics": "检测到多实例，当前按单实例转换",
}

IGNORED_BPMN_TAGS = {
    "definitions",
    "process",
    "participant",
    "laneSet",
    "lane",
    "flowNodeRef",
    "documentation",
    "extensionElements",
    "BPMNDiagram",
    "BPMNPlane",
    "BPMNShape",
    "BPMNEdge",
    "Bounds",
    "waypoint",
    "incoming",
    "outgoing",
    "property",
    "dataObject",
    "dataObjectReference",
    "dataStoreReference",
    "textAnnotation",
    "association",
    "categoryValue",
    "category",
    "collaboration",
    "message",
    "timerEventDefinition",
    "messageEventDefinition",
    "signalEventDefinition",
    "conditionalEventDefinition",
    "errorEventDefinition",
    "escalationEventDefinition",
    "cancelEventDefinition",
    "compensateEventDefinition",
    "linkEventDefinition",
    "terminateEventDefinition",
    "multiInstanceLoopCharacteristics",
    "standardLoopCharacteristics",
    "loopCharacteristics",
}


def _strip_namespace(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _display_path(path: pathlib.Path) -> str:
    resolved = path.resolve()
    return (
        resolved.relative_to(ROOT).as_posix()
        if resolved.is_relative_to(ROOT)
        else str(resolved).replace("\\", "/")
    )


def _find_bpmn_files(paths: list[pathlib.Path]) -> list[pathlib.Path]:
    files: list[pathlib.Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(sorted(path.rglob("*.bpmn")))
        elif path.suffix.lower() == ".bpmn":
            files.append(path)
    return sorted(set(files))


@dataclass
class ElementCount:
    tag: str
    count: int
    status: str
    note: str = ""


@dataclass
class CompatibilityReport:
    bpmn_file: str
    compatible: bool
    blocking_issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    element_inventory: list[ElementCount] = field(default_factory=list)
    parsed_nodes: int = 0
    parsed_sequence_flows: int = 0
    parsed_message_flows: int = 0
    pnml_places: int = 0
    pnml_transitions: int = 0
    pnml_arcs: int = 0
    mcrl2_generated: bool = False
    mcrl2_syntax_ok: bool | None = None
    mcrl2_syntax_error: str = ""
    bounded_mcrl2_syntax_ok: bool | None = None


def _scan_bpmn_elements(bpmn_path: pathlib.Path) -> dict[str, int]:
    root = ET.parse(bpmn_path).getroot()
    counts: dict[str, int] = {}
    for element in root.iter():
        tag = _strip_namespace(element.tag)
        counts[tag] = counts.get(tag, 0) + 1
    return counts


def _classify_element(tag: str) -> tuple[str, str]:
    if tag in FLOW_NODE_XML_TAGS or tag in FLOW_NODE_TAGS or tag in SUPPORTED_FLOWS:
        return "supported", ""
    if tag in CONTAINER_TAGS:
        return "supported", "子流程容器，展开内部节点"
    if tag in TASK_TAGS:
        return "supported", "专用任务类型，映射为 task"
    if tag in UNSUPPORTED_WITH_WARNING:
        return "warning", UNSUPPORTED_WITH_WARNING[tag]
    if tag in UNSUPPORTED_FLOW_NODES:
        return "unsupported", UNSUPPORTED_FLOW_NODES[tag]
    if tag in IGNORED_BPMN_TAGS:
        return "ignored", "BPMN 元数据或图形信息，转换器不处理"
    if tag.endswith("Gateway") or tag.endswith("Event") or tag.endswith("Task") or tag.endswith("SubProcess"):
        return "unsupported", "未在本地转换器白名单中"
    return "ignored", "非流程语义元素"


def _check_flow_references(model, blocking: list[str], warnings: list[str]) -> None:
    known_nodes = set(model.nodes)
    for flow in {**model.sequence_flows, **model.message_flows}.values():
        if flow.source not in known_nodes:
            blocking.append(
                f"流 {flow.fid} 的 sourceRef={flow.source} 未被本地解析器识别"
            )
        if flow.target not in known_nodes:
            blocking.append(
                f"流 {flow.fid} 的 targetRef={flow.target} 未被本地解析器识别"
            )

    for node_id, node in model.nodes.items():
        incoming_seq = model.incoming_sequence_flows.get(node_id, [])
        outgoing_seq = model.outgoing_sequence_flows.get(node_id, [])
        if node.tag not in {"startEvent", "endEvent"} and not incoming_seq and not outgoing_seq:
            warnings.append(f"节点 {node_id} ({node.tag}) 没有 sequence flow 连接")


def _validate_pnml(net, blocking: list[str], warnings: list[str]) -> None:
    place_ids = set(net.places)
    transition_ids = set(net.transitions)
    for arc in net.arcs:
        if arc.source not in place_ids and arc.source not in transition_ids:
            blocking.append(f"弧 {arc.aid} 的 source={arc.source} 不存在")
        if arc.target not in place_ids and arc.target not in transition_ids:
            blocking.append(f"弧 {arc.aid} 的 target={arc.target} 不存在")

    if not net.places:
        blocking.append("PNML 中没有 place")
    if not net.transitions:
        blocking.append("PNML 中没有 transition")
    if not net.arcs:
        blocking.append("PNML 中没有 arc")

    initial_tokens = sum(place.tokens for place in net.places.values())
    if initial_tokens == 0:
        warnings.append("初始 marking 中没有任何 token，模型可能无法启动")


def _run_mcrl22lps(mcrl2_path: pathlib.Path, timeout: int) -> tuple[bool, str]:
    try:
        tool = resolve_tool("mcrl22lps")
    except RuntimeError:
        return False, "mcrl22lps 未安装"
    with tempfile.TemporaryDirectory() as tmp_dir:
        lps_path = pathlib.Path(tmp_dir) / "model.lps"
        result = subprocess.run(
            [tool, str(mcrl2_path), str(lps_path)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    combined = (result.stdout + result.stderr).strip()
    if result.returncode == 0:
        return True, ""
    return False, combined or f"mcrl22lps exited with code {result.returncode}"


def analyze_bpmn(bpmn_path: pathlib.Path, timeout: int = 120) -> CompatibilityReport:
    rel_path = (
        bpmn_path.relative_to(ROOT).as_posix()
        if bpmn_path.is_relative_to(ROOT)
        else str(bpmn_path).replace("\\", "/")
    )
    report = CompatibilityReport(bpmn_file=rel_path, compatible=True)

    raw_counts = _scan_bpmn_elements(bpmn_path)
    semantic_tags = sorted(
        tag
        for tag in raw_counts
        if tag.endswith(("Gateway", "Event", "Task", "SubProcess"))
        or tag in SUPPORTED_FLOWS
        or tag in {"task", "callActivity", "transaction"}
    )
    for tag in semantic_tags:
        status, note = _classify_element(tag)
        report.element_inventory.append(
            ElementCount(tag=tag, count=raw_counts[tag], status=status, note=note)
        )
        if status == "unsupported":
            report.compatible = False
            report.blocking_issues.append(
                f"发现不支持的 BPMN 元素 {tag} x{raw_counts[tag]}：{note}"
            )
        elif status == "warning":
            report.warnings.append(f"发现近似处理的 BPMN 元素 {tag} x{raw_counts[tag]}：{note}")

    try:
        model = parse_bpmn(bpmn_path)
    except Exception as exc:  # noqa: BLE001
        report.compatible = False
        report.blocking_issues.append(f"BPMN 解析失败: {exc}")
        return report

    report.parsed_nodes = len(model.nodes)
    report.parsed_sequence_flows = len(model.sequence_flows)
    report.parsed_message_flows = len(model.message_flows)

    _check_flow_references(model, report.blocking_issues, report.warnings)
    report.warnings.extend(model.warnings)
    if report.blocking_issues:
        report.compatible = False

    try:
        net = convert_bpmn_to_pn(model)
    except Exception as exc:  # noqa: BLE001
        report.compatible = False
        report.blocking_issues.append(f"BPMN -> PNML 转换失败: {exc}")
        return report

    report.pnml_places = len(net.places)
    report.pnml_transitions = len(net.transitions)
    report.pnml_arcs = len(net.arcs)
    _validate_pnml(net, report.blocking_issues, report.warnings)
    if report.blocking_issues:
        report.compatible = False

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = pathlib.Path(tmp_dir)
        pnml_path = tmp / "model.pnml"
        mcrl2_path = tmp / "model.mcrl2"
        bounded_mcrl2_path = tmp / "model_bounded.mcrl2"

        from bpmn2pnml_local import write_pnml

        write_pnml(net, pnml_path)
        try:
            parsed = parse_pnml(pnml_path)
            if len(parsed.places) != report.pnml_places:
                report.warnings.append("PNML 写回后再解析的 place 数量不一致")
        except Exception as exc:  # noqa: BLE001
            report.compatible = False
            report.blocking_issues.append(f"PNML 解析失败: {exc}")
            return report

        try:
            convert_pnml_to_mcrl2(pnml_path, mcrl2_path)
            report.mcrl2_generated = True
        except Exception as exc:  # noqa: BLE001
            report.compatible = False
            report.blocking_issues.append(f"PNML -> mCRL2 转换失败: {exc}")
            return report

        try:
            resolve_tool("mcrl22lps")
        except RuntimeError:
            report.warnings.append("未检测到 mcrl22lps，跳过 mCRL2 语法验证")
            report.mcrl2_syntax_ok = None
            report.bounded_mcrl2_syntax_ok = None
            return report

        ok, error = _run_mcrl22lps(mcrl2_path, timeout)
        report.mcrl2_syntax_ok = ok
        report.mcrl2_syntax_error = error
        if not ok:
            report.compatible = False
            report.blocking_issues.append(f"mCRL2 语法验证失败: {error}")

        convert_pnml_to_mcrl2(pnml_path, bounded_mcrl2_path, max_place_tokens=1)
        bounded_ok, bounded_error = _run_mcrl22lps(bounded_mcrl2_path, timeout)
        report.bounded_mcrl2_syntax_ok = bounded_ok
        if not bounded_ok:
            report.warnings.append(f"bounded mCRL2 语法验证失败: {bounded_error}")

    return report


def write_markdown(reports: list[CompatibilityReport], output_path: pathlib.Path) -> None:
    lines = [
        "# BPMN 转换兼容性报告",
        "",
        "检查范围：本地 `bpmn2pnml_local.py` + `pnml2mcrl2.py` 流水线。",
        "",
        "## 支持矩阵",
        "",
        "| BPMN 元素 | 状态 |",
        "| --- | --- |",
    ]
    for tag in sorted(FLOW_NODE_TAGS):
        lines.append(f"| `{tag}` | 支持 |")
    for tag in sorted(SUPPORTED_FLOWS):
        lines.append(f"| `{tag}` | 支持 |")
    for tag, note in sorted(UNSUPPORTED_FLOW_NODES.items()):
        lines.append(f"| `{tag}` | 不支持（{note}） |")

    lines.extend(["", "## 检查结果", ""])
    for report in reports:
        status = "兼容" if report.compatible else "不兼容"
        lines.extend(
            [
                f"### `{report.bpmn_file}` — {status}",
                "",
                f"- 解析节点：{report.parsed_nodes}",
                f"- sequence flow：{report.parsed_sequence_flows}",
                f"- message flow：{report.parsed_message_flows}",
                f"- PNML：{report.pnml_places} places / {report.pnml_transitions} transitions / {report.pnml_arcs} arcs",
                f"- mCRL2 已生成：{str(report.mcrl2_generated).lower()}",
                f"- mCRL2 语法验证：{report.mcrl2_syntax_ok}",
                f"- bounded mCRL2 语法验证：{report.bounded_mcrl2_syntax_ok}",
                "",
            ]
        )
        if report.element_inventory:
            lines.append("| 元素 | 数量 | 状态 | 说明 |")
            lines.append("| --- | ---: | --- | --- |")
            for item in report.element_inventory:
                lines.append(
                    f"| `{item.tag}` | {item.count} | {item.status} | {item.note} |"
                )
            lines.append("")
        if report.blocking_issues:
            lines.append("**阻塞问题：**")
            for issue in report.blocking_issues:
                lines.append(f"- {issue}")
            lines.append("")
        if report.warnings:
            lines.append("**警告：**")
            for warning in report.warnings:
                lines.append(f"- {warning}")
            lines.append("")

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Check BPMN compatibility with the local conversion pipeline")
    parser.add_argument(
        "inputs",
        nargs="*",
        type=pathlib.Path,
        default=[ROOT / "examples"],
        help="BPMN files or directories (default: examples/)",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=pathlib.Path,
        default=ROOT / "docs" / "compatibility",
        help="Directory for JSON/Markdown reports",
    )
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()

    bpmn_files = _find_bpmn_files(args.inputs)
    if not bpmn_files:
        raise SystemExit("No BPMN files found")

    reports = [analyze_bpmn(path, timeout=args.timeout) for path in bpmn_files]
    args.output_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "supported_flow_nodes": sorted(FLOW_NODE_TAGS),
        "supported_flows": sorted(SUPPORTED_FLOWS),
        "unsupported_flow_nodes": UNSUPPORTED_FLOW_NODES,
        "summary": {
            "total": len(reports),
            "compatible": sum(1 for report in reports if report.compatible),
            "incompatible": sum(1 for report in reports if not report.compatible),
        },
        "reports": [
            {
                **asdict(report),
                "element_inventory": [asdict(item) for item in report.element_inventory],
            }
            for report in reports
        ],
    }
    json_path = args.output_dir / "compatibility_report.json"
    md_path = args.output_dir / "compatibility_report.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_markdown(reports, md_path)

    print(json.dumps(payload["summary"], indent=2))
    print(f"Report written to {_display_path(json_path)}")
    print(f"Report written to {_display_path(md_path)}")
    raise SystemExit(0 if payload["summary"]["incompatible"] == 0 else 1)


if __name__ == "__main__":
    main()
