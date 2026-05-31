#!/usr/bin/env python3
"""Run reproducible comparison between local and SpringOxO converters."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def run_cmd(command: list[str], cwd: Path) -> dict[str, Any]:
    started = time.perf_counter()
    proc = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )
    elapsed = time.perf_counter() - started
    return {
        "command": " ".join(command),
        "returncode": proc.returncode,
        "ok": proc.returncode == 0,
        "elapsed_seconds": round(elapsed, 4),
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def strip_ns(tag: str) -> str:
    return tag.split("}", 1)[-1]


def parse_bpmn_stats(path: Path) -> dict[str, Any]:
    tree = ET.parse(path)
    root = tree.getroot()
    counts: dict[str, int] = {}
    for elem in root.iter():
        tag = strip_ns(elem.tag)
        counts[tag] = counts.get(tag, 0) + 1

    focus_tags = [
        "participant",
        "process",
        "task",
        "userTask",
        "serviceTask",
        "sendTask",
        "receiveTask",
        "subProcess",
        "eventBasedGateway",
        "parallelGateway",
        "exclusiveGateway",
        "messageFlow",
        "sequenceFlow",
        "boundaryEvent",
        "startEvent",
        "endEvent",
        "intermediateCatchEvent",
        "intermediateThrowEvent",
    ]
    feature_counts = {tag: counts.get(tag, 0) for tag in focus_tags}
    return {
        "path": str(path),
        "feature_counts": feature_counts,
    }


def parse_pnml_stats(path: Path) -> dict[str, Any]:
    tree = ET.parse(path)
    root = tree.getroot()
    places = 0
    transitions = 0
    arcs = 0
    initial_tokens = 0
    places_with_initial_tokens = 0
    for elem in root.iter():
        tag = strip_ns(elem.tag)
        if tag == "place":
            places += 1
            has_tokens = 0
            for child in elem.iter():
                if strip_ns(child.tag) == "initialMarking":
                    text_node = child.find(".//")
                    if text_node is not None and text_node.text and text_node.text.strip().isdigit():
                        has_tokens = int(text_node.text.strip())
                    break
            initial_tokens += has_tokens
            if has_tokens > 0:
                places_with_initial_tokens += 1
        elif tag == "transition":
            transitions += 1
        elif tag == "arc":
            arcs += 1
    return {
        "path": str(path),
        "places": places,
        "transitions": transitions,
        "arcs": arcs,
        "initial_tokens": initial_tokens,
        "places_with_initial_tokens": places_with_initial_tokens,
    }


def extract_between(text: str, start_keyword: str, end_keyword: str) -> str:
    pattern = re.compile(rf"{start_keyword}(.*?){end_keyword}", re.DOTALL)
    match = pattern.search(text)
    return match.group(1) if match else ""


def parse_actions(mcrl2_text: str) -> list[str]:
    block = extract_between(mcrl2_text, r"\bact\b", r"\bproc\b")
    if not block:
        return []

    actions: list[str] = []
    for segment in block.split(";"):
        left = segment.split(":", 1)[0]
        for token in left.replace("\n", " ").split(","):
            action = token.strip()
            if action:
                actions.append(action)
    # Keep stable uniqueness order.
    seen: set[str] = set()
    deduped: list[str] = []
    for action in actions:
        if action not in seen:
            seen.add(action)
            deduped.append(action)
    return deduped


def parse_process_count(mcrl2_text: str) -> int:
    block = extract_between(mcrl2_text, r"\bproc\b", r"\binit\b")
    if not block:
        return 0
    return len(re.findall(r"^\s*[A-Za-z_][A-Za-z0-9_]*\s*\(", block, flags=re.MULTILINE))


def parse_comm_rule_count(mcrl2_text: str) -> int:
    match = re.search(r"comm\(\{(.*?)\},", mcrl2_text, flags=re.DOTALL)
    if not match:
        return 0
    body = match.group(1)
    return body.count("->")


def parse_allow_action_count(mcrl2_text: str) -> int:
    match = re.search(r"allow\(\{(.*?)\},", mcrl2_text, flags=re.DOTALL)
    if not match:
        return 0
    body = match.group(1)
    return len([token for token in body.replace("\n", " ").split(",") if token.strip()])


def summarize_action_readability(actions: list[str]) -> dict[str, Any]:
    valid_pattern = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
    valid_names = [a for a in actions if valid_pattern.match(a)]
    invalid_names = [a for a in actions if not valid_pattern.match(a)]
    send_actions = [a for a in actions if a.startswith("s_")]
    recv_actions = [a for a in actions if a.startswith("r_")]
    comm_actions = [a for a in actions if a.startswith("c_")]
    generic_actions = [a for a in actions if a.startswith("fire_")]

    return {
        "total_actions": len(actions),
        "valid_mcrl2_identifiers": len(valid_names),
        "invalid_mcrl2_identifiers": invalid_names,
        "send_actions": len(send_actions),
        "receive_actions": len(recv_actions),
        "communication_actions": len(comm_actions),
        "generic_fire_actions": len(generic_actions),
    }


def validate_mcrl2_syntax(mcrl2_file: Path) -> dict[str, Any]:
    tool = shutil.which("mcrl22lps")
    if not tool:
        return {
            "tool_available": False,
            "ok": None,
            "message": "mcrl22lps not found in PATH",
        }

    target_lps = mcrl2_file.with_suffix(".lps")
    result = run_cmd([tool, str(mcrl2_file), str(target_lps)], cwd=mcrl2_file.parent)
    return {
        "tool_available": True,
        "ok": result["ok"],
        "returncode": result["returncode"],
        "stdout": result["stdout"],
        "stderr": result["stderr"],
    }


def parse_mcrl2_stats(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    actions = parse_actions(text)
    return {
        "path": str(path),
        "line_count": len(lines),
        "process_count": parse_process_count(text),
        "allow_action_count": parse_allow_action_count(text),
        "comm_rule_count": parse_comm_rule_count(text),
        "action_readability": summarize_action_readability(actions),
        "syntax_validation": validate_mcrl2_syntax(path),
    }


def execute_pipeline(
    repo_root: Path,
    spring_repo_root: Path,
    input_bpmn: Path,
    out_dir: Path,
) -> dict[str, Any]:
    stem = input_bpmn.stem
    local_pnml = out_dir / f"local_{stem}.pnml"
    local_mcrl2 = out_dir / f"local_{stem}.mcrl2"
    spring_mcrl2 = out_dir / f"springoxo_{stem}.mcrl2"

    cmd_local_1 = ["python", "bpmn2pnml_local.py", str(input_bpmn), "-o", str(local_pnml)]
    cmd_local_2 = ["python", "pnml2mcrl2.py", str(local_pnml), "-o", str(local_mcrl2)]
    cmd_spring = [
        "python",
        str(spring_repo_root / "scripts" / "bpmn2mcrl2.py"),
        str(input_bpmn),
        str(spring_mcrl2),
    ]

    run_local_1 = run_cmd(cmd_local_1, cwd=repo_root)
    run_local_2 = run_cmd(cmd_local_2, cwd=repo_root) if run_local_1["ok"] else None
    run_spring = run_cmd(cmd_spring, cwd=repo_root)

    local_ok = run_local_1["ok"] and bool(run_local_2 and run_local_2["ok"])
    spring_ok = run_spring["ok"]
    both_ok = local_ok and spring_ok

    result: dict[str, Any] = {
        "input_bpmn": str(input_bpmn),
        "commands": {
            "local_bpmn_to_pnml": run_local_1,
            "local_pnml_to_mcrl2": run_local_2,
            "springoxo_bpmn_to_mcrl2": run_spring,
        },
        "success": {
            "local": local_ok,
            "springoxo": spring_ok,
            "both": both_ok,
        },
    }

    if local_ok:
        result["local_outputs"] = {
            "pnml": parse_pnml_stats(local_pnml),
            "mcrl2": parse_mcrl2_stats(local_mcrl2),
        }
    if spring_ok:
        result["springoxo_outputs"] = {
            "mcrl2": parse_mcrl2_stats(spring_mcrl2),
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare local converter with SpringOxO method")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(".").resolve(),
        help="Current repository root",
    )
    parser.add_argument(
        "--spring-repo-root",
        type=Path,
        default=Path("/tmp/springoxo_bpmn2mcrl2"),
        help="Downloaded SpringOxO repo root",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("docs/comparison/springoxo_vs_local/results.json"),
        help="JSON output path",
    )
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    spring_repo_root = args.spring_repo_root.resolve()
    output_json = args.output_json.resolve()
    comparison_dir = output_json.parent
    result_dir = comparison_dir / "results"
    result_dir.mkdir(parents=True, exist_ok=True)

    candidate_inputs = [
        repo_root / "examples/pizza_official.bpmn",
        repo_root / "examples/pizza.bpmn",
    ]

    attempts: list[dict[str, Any]] = []
    selected: dict[str, Any] | None = None
    for input_bpmn in candidate_inputs:
        if not input_bpmn.exists():
            continue
        attempt = execute_pipeline(repo_root, spring_repo_root, input_bpmn, result_dir)
        attempts.append(attempt)
        if attempt["success"]["both"]:
            selected = attempt
            break

    summary = {
        "generated_at_epoch": int(time.time()),
        "repo_root": str(repo_root),
        "spring_repo_root": str(spring_repo_root),
        "source_bpmn_stats": parse_bpmn_stats(selected["input_bpmn"]) if selected else None,
        "selected_run": selected,
        "attempts": attempts,
        "selection_policy": "prefer examples/pizza_official.bpmn; fallback examples/pizza.bpmn only when needed",
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote comparison results to {output_json}")


if __name__ == "__main__":
    main()
