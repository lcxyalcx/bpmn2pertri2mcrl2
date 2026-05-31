#!/usr/bin/env python3
"""Run benchmark BPMN coverage suite and export compatibility reports."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_bpmn_compatibility import analyze_bpmn  # noqa: E402

DEFAULT_MANIFEST = ROOT / "examples" / "benchmarks" / "suite_manifest.json"
DEFAULT_OUTPUT_DIR = ROOT / "docs" / "compatibility" / "benchmarks"


def _to_posix(path: pathlib.Path) -> str:
    if path.is_relative_to(ROOT):
        return path.relative_to(ROOT).as_posix()
    return str(path).replace("\\", "/")


def load_manifest(manifest_path: pathlib.Path) -> dict[str, object]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if "scenarios" not in payload or not isinstance(payload["scenarios"], list):
        raise ValueError("Manifest must contain a list field: scenarios")
    return payload


def run_suite(
    manifest_path: pathlib.Path,
    output_dir: pathlib.Path,
    timeout: int = 120,
) -> dict[str, object]:
    manifest = load_manifest(manifest_path)
    scenarios: list[dict[str, object]] = manifest["scenarios"]  # type: ignore[assignment]

    results: list[dict[str, object]] = []
    category_summary: dict[str, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "compatible": 0, "incompatible": 0}
    )

    for scenario in scenarios:
        scenario_id = str(scenario["id"])
        rel_file = pathlib.Path(str(scenario["file"]))
        categories = [str(item) for item in scenario.get("categories", [])]
        focus = str(scenario.get("focus", ""))

        model_path = (ROOT / rel_file).resolve()
        if not model_path.exists():
            raise FileNotFoundError(f"Scenario {scenario_id} file not found: {rel_file}")

        report = analyze_bpmn(model_path, timeout=timeout)
        result = {
            "id": scenario_id,
            "file": _to_posix(model_path),
            "focus": focus,
            "categories": categories,
            "compatible": report.compatible,
            "parsed_nodes": report.parsed_nodes,
            "parsed_sequence_flows": report.parsed_sequence_flows,
            "parsed_message_flows": report.parsed_message_flows,
            "pnml_places": report.pnml_places,
            "pnml_transitions": report.pnml_transitions,
            "pnml_arcs": report.pnml_arcs,
            "blocking_issues": report.blocking_issues,
            "warnings": report.warnings,
        }
        results.append(result)

        for category in categories:
            row = category_summary[category]
            row["total"] += 1
            if report.compatible:
                row["compatible"] += 1
            else:
                row["incompatible"] += 1

    summary = {
        "suite_name": manifest.get("suite_name", "unnamed_suite"),
        "manifest": _to_posix(manifest_path.resolve()),
        "total": len(results),
        "compatible": sum(1 for item in results if item["compatible"]),
        "incompatible": sum(1 for item in results if not item["compatible"]),
        "category_summary": dict(category_summary),
    }
    payload = {
        "summary": summary,
        "results": results,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "benchmark_suite_report.json"
    md_path = output_dir / "benchmark_suite_report.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_markdown(payload, md_path)
    return payload


def write_markdown(payload: dict[str, object], output_path: pathlib.Path) -> None:
    summary = payload["summary"]
    results = payload["results"]
    lines = [
        "# BPMN 基准样例覆盖报告",
        "",
        f"- 套件：`{summary['suite_name']}`",
        f"- 样例总数：{summary['total']}",
        f"- 兼容：{summary['compatible']}",
        f"- 不兼容：{summary['incompatible']}",
        "",
        "## 分类汇总",
        "",
        "| 分类 | 总数 | 兼容 | 不兼容 |",
        "| --- | ---: | ---: | ---: |",
    ]
    for category, row in sorted(summary["category_summary"].items()):
        lines.append(
            f"| `{category}` | {row['total']} | {row['compatible']} | {row['incompatible']} |"
        )

    lines.extend(["", "## 场景结果", "", "| 场景 | 文件 | 重点 | 结果 | 备注 |", "| --- | --- | --- | --- | --- |"])
    for item in results:
        status = "兼容" if item["compatible"] else "不兼容"
        note = f"{len(item['warnings'])} warnings"
        if item["blocking_issues"]:
            note = f"{len(item['blocking_issues'])} blocking"
        lines.append(
            f"| `{item['id']}` | `{item['file']}` | {item['focus']} | {status} | {note} |"
        )

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run BPMN benchmark compatibility suite")
    parser.add_argument(
        "--manifest",
        type=pathlib.Path,
        default=DEFAULT_MANIFEST,
        help="Benchmark suite manifest path",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=pathlib.Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Output directory for benchmark suite report",
    )
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()

    payload = run_suite(args.manifest, args.output_dir, timeout=args.timeout)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))
    if payload["summary"]["incompatible"] > 0:
        raise SystemExit(1)
    raise SystemExit(0)


if __name__ == "__main__":
    main()
