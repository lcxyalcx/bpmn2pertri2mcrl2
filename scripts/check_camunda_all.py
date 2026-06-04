#!/usr/bin/env python3
"""Run bounded LTS and key action checks for the Camunda all.bpmn model."""

from __future__ import annotations

import argparse
import html
import json
import pathlib
import re
import subprocess
import sys
from dataclasses import dataclass


ROOT = pathlib.Path(__file__).resolve().parents[1]
CAMUNDA_BPMN = ROOT / "Camunda-all-main" / "merged_code" / "bpmn" / "all.bpmn"
PROPERTIES_DIR = ROOT / "properties" / "camunda_all"
OUTPUT_DIR = ROOT / "docs" / "verification" / "camunda_all"
sys.path.insert(0, str(ROOT))

from bpmn2pnml_local import convert_file as convert_bpmn_to_pnml  # noqa: E402
from pnml2mcrl2 import convert_file as convert_pnml_to_mcrl2  # noqa: E402
from scripts.verification_utils import parse_bool_result, parse_ltsinfo, resolve_tool, write_lts_svg  # noqa: E402


def rel(path: pathlib.Path) -> str:
    return path.relative_to(ROOT).as_posix()


@dataclass(frozen=True)
class PropertySpec:
    file_name: str
    title: str
    expected: bool
    note: str
    action: str


PROPERTIES = [
    PropertySpec(
        "order_to_ffw_reachable.mcf",
        "Order reaches freight forwarder",
        True,
        "Owner can publish order-to-ffw.",
        "order_to_ffw",
    ),
    PropertySpec(
        "customs_clearance_to_terminal_reachable.mcf",
        "Customs clearance reaches terminal",
        False,
        "Not observed within the default 2000-state partial LTS; increase --max-lts-states or run a dedicated solver check for deeper reachability.",
        "customs_clearance_to_terminal",
    ),
    PropertySpec(
        "ctn_to_owner_reachable.mcf",
        "Container reaches owner",
        False,
        "Not observed within the default 2000-state partial LTS; increase --max-lts-states or run a dedicated solver check for deeper reachability.",
        "ctn_to_owner",
    ),
    PropertySpec(
        "ship_departure_notification_reachable.mcf",
        "Ship departure notification is reachable",
        False,
        "Not observed within the default 2000-state partial LTS; increase --max-lts-states or run a dedicated solver check for deeper reachability.",
        "ship_departure_notification",
    ),
    PropertySpec(
        "payment_reachable.mcf",
        "Payment is reachable",
        False,
        "Not observed within the default 2000-state partial LTS; increase --max-lts-states or run a dedicated solver check for deeper reachability.",
        "payment",
    ),
    PropertySpec(
        "joined_end_reachable.mcf",
        "Joined end is reachable",
        False,
        "Not observed within the default 2000-state partial LTS; this full-system end is expected to require deeper exploration.",
        "a_end",
    ),
    PropertySpec(
        "order_to_ffw_requires_handle_order.mcf",
        "Order-to-FFW requires handle-order",
        True,
        "No explored path publishes order-to-ffw before handle-order.",
        "handle_order -> order_to_ffw",
    ),
    PropertySpec(
        "order_received_requires_order_to_ffw.mcf",
        "Order received requires order-to-FFW",
        True,
        "No explored path reaches order-received before order-to-ffw.",
        "order_to_ffw -> order_received",
    ),
    PropertySpec(
        "parallel_gateway_order_a_before_b.mcf",
        "Gateway 0ujvw7r can precede gateway 1mop6g2",
        True,
        "The bounded LTS contains one behavior where gateway 0ujvw7r occurs before gateway 1mop6g2.",
        "parallel_gateway_gateway_0ujvw7r -> parallel_gateway_gateway_1mop6g2",
    ),
    PropertySpec(
        "parallel_gateway_order_b_before_a.mcf",
        "Gateway 1mop6g2 can precede gateway 0ujvw7r",
        True,
        "The bounded LTS also contains the reverse order, so observers must not assume a fixed order between these parallel gateway effects.",
        "parallel_gateway_gateway_1mop6g2 -> parallel_gateway_gateway_0ujvw7r",
    ),
]


@dataclass(frozen=True)
class WitnessSpec:
    action: str
    title: str
    note: str


CUSTOMS_WITNESSES = [
    WitnessSpec(
        "manifest_received",
        "Customs receives manifest",
        "One of the three customs synchronization inputs is reachable with targeted depth-first exploration.",
    ),
    WitnessSpec(
        "ctn_and_ship_arrive",
        "Customs receives container and ship arrival",
        "The terminal arrival input for the customs synchronization point is reachable.",
    ),
    WitnessSpec(
        "declaration_received",
        "Customs receives declaration",
        "The broker declaration input for the customs synchronization point is reachable.",
    ),
    WitnessSpec(
        "clearance_to_broker",
        "Customs sends clearance to broker",
        "The broker-facing customs clearance response is reachable.",
    ),
    WitnessSpec(
        "inspection_appointment",
        "Broker sends inspection appointment",
        "The broker-side follow-up after customs clearance-to-broker is reachable.",
    ),
    WitnessSpec(
        "ciq",
        "Customs CIQ check is reachable",
        "After the customs synchronization point, CIQ can execute.",
    ),
    WitnessSpec(
        "inspection",
        "Customs inspection is reachable",
        "The customs inspection step after CIQ can execute.",
    ),
    WitnessSpec(
        "customs_clearance_to_terminal",
        "Customs clearance reaches terminal",
        "The terminal-facing customs clearance output is reachable with targeted depth-first exploration.",
    ),
]


def run(
    cmd: list[str],
    timeout: int = 120,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
        timeout=timeout,
    )


def parse_action_found(output: str, action: str) -> tuple[bool, int | None]:
    pattern = rf"Action '{re.escape(action)}' found \(state index: (\d+)\)"
    match = re.search(pattern, output)
    if match:
        return True, int(match.group(1))
    return False, None


def write_summary_svg(results: list[dict[str, object]], svg_path: pathlib.Path) -> None:
    width = 980
    row_height = 74
    height = 110 + row_height * len(results)
    rows = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="32" y="42" font-family="Helvetica" font-size="24" font-weight="700">Camunda all.bpmn verification summary</text>',
        '<text x="32" y="70" font-family="Helvetica" font-size="14" fill="#475569">Default checks scan the generated partial bounded LTS; deeper properties may require a higher state limit.</text>',
    ]
    y = 98
    for result in results:
        passed = bool(result["passed"])
        expected = bool(result["expected"])
        ok = passed == expected
        fill = "#dcfce7" if ok else "#fee2e2"
        stroke = "#16a34a" if ok else "#dc2626"
        rows.extend(
            [
                f'<rect x="32" y="{y}" width="916" height="54" rx="8" fill="{fill}" stroke="{stroke}"/>',
                f'<text x="52" y="{y + 22}" font-family="Helvetica" font-size="15" font-weight="700">{html.escape(str(result["title"]))}</text>',
                f'<text x="52" y="{y + 42}" font-family="Helvetica" font-size="13" fill="#334155">result={str(passed).lower()} · expected={str(expected).lower()} · {html.escape(str(result["note"]))}</text>',
            ]
        )
        y += row_height
    rows.append("</svg>")
    svg_path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Camunda all.bpmn bounded LTS generation and action checks"
    )
    parser.add_argument("--max-place-tokens", type=int, default=1)
    parser.add_argument("--max-lts-states", type=int, default=2000)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--bpmn", type=pathlib.Path, default=CAMUNDA_BPMN)
    args = parser.parse_args()

    mcrl22lps = resolve_tool("mcrl22lps")
    lps2lts = resolve_tool("lps2lts")
    ltsconvert = resolve_tool("ltsconvert")
    lts2pbes = resolve_tool("lts2pbes")
    pbes2bool = resolve_tool("pbes2bool")
    ltsinfo = resolve_tool("ltsinfo")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    pnml_path = OUTPUT_DIR / "camunda_all.pnml"
    bounded_mcrl2 = OUTPUT_DIR / "camunda_all_bounded.mcrl2"
    lps_path = OUTPUT_DIR / "camunda_all_bounded.lps"
    lts_path = OUTPUT_DIR / "camunda_all_bounded.lts"
    lts_dot_path = OUTPUT_DIR / "camunda_all_bounded_lts.dot"
    lts_aut_path = OUTPUT_DIR / "camunda_all_bounded_lts.aut"
    lts_svg_path = OUTPUT_DIR / "camunda_all_bounded_lts.svg"

    convert_bpmn_to_pnml(args.bpmn, pnml_path)
    convert_pnml_to_mcrl2(
        pnml_path,
        bounded_mcrl2,
        max_place_tokens=args.max_place_tokens,
    )
    run([mcrl22lps, str(bounded_mcrl2), str(lps_path)], timeout=args.timeout)
    run([lps2lts, f"--max={args.max_lts_states}", str(lps_path), str(lts_path)], timeout=args.timeout)
    run([ltsconvert, "--out=dot", str(lts_path), str(lts_dot_path)], timeout=args.timeout)
    run([ltsconvert, "--out=aut", str(lts_path), str(lts_aut_path)], timeout=args.timeout)
    write_lts_svg(lts_aut_path, lts_svg_path, max_states=160)
    lts_info_result = run([ltsinfo, str(lts_path)], timeout=args.timeout)
    lts_info = parse_ltsinfo(lts_info_result.stdout + lts_info_result.stderr)

    results: list[dict[str, object]] = []
    for spec in PROPERTIES:
        formula = PROPERTIES_DIR / spec.file_name
        pbes_path = OUTPUT_DIR / f"{formula.stem}_lts.pbes"
        run(
            [
                lts2pbes,
                "--preprocess-modal-operators",
                f"--formula={formula}",
                f"--lps={lps_path}",
                str(lts_path),
                str(pbes_path),
            ],
            timeout=args.timeout,
        )
        solved = run([pbes2bool, str(pbes_path)], timeout=args.timeout)
        solver_output = (solved.stdout + solved.stderr).strip()
        passed = parse_bool_result(solver_output)
        results.append(
            {
                "file": rel(formula),
                "pbes": rel(pbes_path),
                "backend": "lts2pbes+pbes2bool",
                "title": spec.title,
                "action": spec.action,
                "passed": passed,
                "expected": spec.expected,
                "matches_expected": passed == spec.expected,
                "note": spec.note,
                "solver_output": solver_output,
            }
        )

    customs_witnesses: list[dict[str, object]] = []
    for spec in CUSTOMS_WITNESSES:
        witness_path = OUTPUT_DIR / f"{spec.action}_targeted_witness.lts"
        found = run(
            [
                lps2lts,
                "--cached",
                "--strategy=depth",
                f"--action={spec.action}",
                "--trace=1",
                "--max=50000",
                str(lps_path),
                str(witness_path),
            ],
            timeout=args.timeout,
            check=False,
        )
        combined = found.stdout + found.stderr
        passed, state_index = parse_action_found(combined, spec.action)
        customs_witnesses.append(
            {
                "action": spec.action,
                "title": spec.title,
                "passed": passed,
                "state_index": state_index,
                "backend": "lps2lts --action --trace=1 --strategy=depth",
                "note": spec.note,
                "tool_exit_code": found.returncode,
                "tool_output": combined.strip(),
            }
        )

    summary_svg = OUTPUT_DIR / "camunda_all_verification_summary.svg"
    write_summary_svg(results, summary_svg)

    summary = {
        "input_bpmn": rel(args.bpmn.resolve()),
        "pnml": rel(pnml_path),
        "bounded_model": rel(bounded_mcrl2),
        "max_place_tokens": args.max_place_tokens,
        "max_lts_states": args.max_lts_states,
        "lps": rel(lps_path),
        "lts": rel(lts_path),
        "lts_dot": rel(lts_dot_path),
        "lts_aut": rel(lts_aut_path),
        "lts_svg": rel(lts_svg_path),
        "summary_svg": rel(summary_svg),
        "lts_info": lts_info,
        "properties": results,
        "customs_witnesses": customs_witnesses,
    }
    (OUTPUT_DIR / "results.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )

    markdown_lines = [
        "# Camunda all.bpmn Verification Results",
        "",
        f"- Input BPMN: `{summary['input_bpmn']}`",
        f"- PNML: `{summary['pnml']}`",
        f"- Bounded model: `{summary['bounded_model']}`",
        f"- Bound: each place is limited to at most {args.max_place_tokens} token(s)",
        f"- Visualization limit: first {args.max_lts_states} generated states",
        f"- LTS SVG: `{summary['lts_svg']}`",
        f"- Summary SVG: `{summary['summary_svg']}`",
        "- Property backend: `lts2pbes + pbes2bool` over the generated partial bounded LTS.",
        "",
        "## LTS",
        "",
    ]
    for key, value in lts_info.items():
        markdown_lines.append(f"- {key}: {value}")
    markdown_lines.extend(["", "## Properties", ""])
    markdown_lines.append("| Property | Action | Result | Expected | Backend | Interpretation |")
    markdown_lines.append("| --- | --- | --- | --- | --- | --- |")
    for result in results:
        markdown_lines.append(
            "| {title} | `{action}` | {passed} | {expected} | `{backend}` | {note} |".format(
                title=result["title"],
                action=result["action"],
                passed=str(result["passed"]).lower(),
                expected=str(result["expected"]).lower(),
                backend=result["backend"],
                note=result["note"],
            )
        )
    markdown_lines.extend(["", "## Customs Scenario Targeted Witnesses", ""])
    markdown_lines.append("| Action | Result | State index | Backend | Interpretation |")
    markdown_lines.append("| --- | --- | --- | --- | --- |")
    for witness in customs_witnesses:
        state_index = witness["state_index"] if witness["state_index"] is not None else "-"
        markdown_lines.append(
            "| {action} | {passed} | {state_index} | `{backend}` | {note} |".format(
                action=witness["action"],
                passed=str(witness["passed"]).lower(),
                state_index=state_index,
                backend=witness["backend"],
                note=witness["note"],
            )
        )
    (OUTPUT_DIR / "README.md").write_text("\n".join(markdown_lines) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
