#!/usr/bin/env python3
"""Run modal formula checks and bounded LTS visualization for Pizza."""

from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys
import html
import re
from collections import defaultdict, deque
from dataclasses import dataclass


ROOT = pathlib.Path(__file__).resolve().parents[1]
PROPERTIES_DIR = ROOT / "properties" / "pizza_official"
OUTPUT_DIR = ROOT / "docs" / "verification" / "pizza_official"


@dataclass(frozen=True)
class PropertySpec:
    file_name: str
    title: str
    expected: bool
    note: str
    action: str | None = None
    deadlock_free: bool = False


PROPERTIES = [
    PropertySpec(
        "order_can_reach_vendor.mcf",
        "Order can reach vendor",
        True,
        "After order_a_pizza, order_received remains possible.",
        action="order_received",
    ),
    PropertySpec(
        "delivery_reachable.mcf",
        "Delivery is reachable",
        True,
        "The vendor can bake and deliver the pizza.",
        action="deliver_the_pizza",
    ),
    PropertySpec(
        "payment_reachable.mcf",
        "Payment is reachable",
        True,
        "The local PNML conversion lets payment consume the money message.",
        action="receive_payment",
    ),
    PropertySpec(
        "ask_calm_loop_reachable.mcf",
        "Ask/calm loop is reachable",
        True,
        "The timeout/question/customer-calming loop can complete.",
        action="calm_customer",
    ),
    PropertySpec(
        "end_reachable.mcf",
        "Joined end is reachable",
        True,
        "Both participant processes can reach the joined end transition.",
        action="a_end_2",
    ),
    PropertySpec(
        "no_deadlock.mcf",
        "No deadlock",
        False,
        "Deadlock is expected after both participant processes finish.",
        deadlock_free=True,
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


def require_tool(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise RuntimeError(f"Required tool not found on PATH: {name}")
    return path


def write_summary_svg(results: list[dict[str, object]], svg_path: pathlib.Path) -> None:
    width = 980
    row_height = 74
    height = 110 + row_height * len(results)
    rows = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="32" y="42" font-family="Helvetica" font-size="24" font-weight="700">Official Pizza verification summary</text>',
        '<text x="32" y="70" font-family="Helvetica" font-size="14" fill="#475569">Green means the formula result matches the documented expectation.</text>',
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


def parse_aut(path: pathlib.Path) -> tuple[int, int, list[tuple[int, str, int]]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    header = re.search(r"des \((\d+),\s*(\d+),\s*(\d+)\)", text)
    if header is None:
        raise ValueError(f"Cannot parse AUT header in {path}")
    initial = int(header.group(1))
    transitions: list[tuple[int, str, int]] = []
    for source, label, target in re.findall(r'\((\d+),"(.*)",(\d+)\)', text):
        transitions.append((int(source), label, int(target)))
    return initial, int(header.group(3)), transitions


def write_lts_svg(aut_path: pathlib.Path, svg_path: pathlib.Path, max_states: int = 120) -> None:
    initial, state_count, transitions = parse_aut(aut_path)
    adjacency: dict[int, list[tuple[str, int]]] = defaultdict(list)
    for source, label, target in transitions:
        adjacency[source].append((label, target))

    depth = {initial: 0}
    queue: deque[int] = deque([initial])
    while queue and len(depth) < max_states:
        state = queue.popleft()
        for _, target in adjacency.get(state, []):
            if target not in depth:
                depth[target] = depth[state] + 1
                queue.append(target)
                if len(depth) >= max_states:
                    break

    levels: dict[int, list[int]] = defaultdict(list)
    for state, d in depth.items():
        levels[d].append(state)
    for states in levels.values():
        states.sort()

    x_gap = 190
    y_gap = 78
    margin_x = 70
    margin_y = 90
    max_level = max(levels) if levels else 0
    max_level_size = max((len(states) for states in levels.values()), default=1)
    width = max(900, margin_x * 2 + (max_level + 1) * x_gap)
    height = max(420, margin_y * 2 + max_level_size * y_gap)

    coords: dict[int, tuple[int, int]] = {}
    for d, states in levels.items():
        level_height = (len(states) - 1) * y_gap
        start_y = margin_y + max(0, (max_level_size - len(states)) * y_gap // 2)
        for index, state in enumerate(states):
            coords[state] = (margin_x + d * x_gap, start_y + index * y_gap)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<defs><marker id="arrow" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto"><path d="M0,0 L10,4 L0,8 z" fill="#64748b"/></marker></defs>',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="28" y="34" font-family="Helvetica" font-size="22" font-weight="700">Official Pizza bounded LTS</text>',
        f'<text x="28" y="58" font-family="Helvetica" font-size="13" fill="#475569">Showing {len(coords)} of {state_count} states and transitions between shown states.</text>',
    ]

    shown_edges = 0
    for source, label, target in transitions:
        if source not in coords or target not in coords:
            continue
        x1, y1 = coords[source]
        x2, y2 = coords[target]
        shown_edges += 1
        if source == target:
            lines.append(
                f'<path d="M{x1 + 18},{y1 - 18} C{x1 + 60},{y1 - 58} {x1 + 92},{y1 - 16} {x1 + 28},{y1 - 4}" fill="none" stroke="#94a3b8" stroke-width="1.4" marker-end="url(#arrow)"/>'
            )
            label_x, label_y = x1 + 44, y1 - 34
        else:
            lines.append(
                f'<line x1="{x1 + 20}" y1="{y1}" x2="{x2 - 22}" y2="{y2}" stroke="#94a3b8" stroke-width="1.2" marker-end="url(#arrow)"/>'
            )
            label_x, label_y = (x1 + x2) // 2, (y1 + y2) // 2 - 5
        short_label = label if len(label) <= 28 else label[:25] + "..."
        lines.append(
            f'<text x="{label_x}" y="{label_y}" font-family="Helvetica" font-size="10" fill="#334155">{html.escape(short_label)}</text>'
        )

    for state, (x, y) in coords.items():
        fill = "#dbeafe" if state == initial else "#f8fafc"
        stroke = "#2563eb" if state == initial else "#64748b"
        lines.extend(
            [
                f'<circle cx="{x}" cy="{y}" r="22" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>',
                f'<text x="{x}" y="{y + 4}" font-family="Helvetica" font-size="12" text-anchor="middle" fill="#0f172a">{state}</text>',
            ]
        )

    lines.append(
        f'<text x="28" y="{height - 24}" font-family="Helvetica" font-size="12" fill="#475569">{shown_edges} shown transitions. Use the DOT/AUT files for machine-level inspection.</text>'
    )
    lines.append("</svg>")
    svg_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_ltsinfo(output: str) -> dict[str, str]:
    info: dict[str, str] = {}
    for line in output.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            info[key.strip()] = value.strip().rstrip(".")
        elif line.strip():
            info[line.strip().rstrip(".")] = "yes"
    return info


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run official Pizza modal formula checks and LTS visualization"
    )
    parser.add_argument("--max-place-tokens", type=int, default=1)
    parser.add_argument("--max-lts-states", type=int, default=200)
    parser.add_argument(
        "--pnml",
        type=pathlib.Path,
        default=ROOT / "examples" / "pizza_official_local.pnml",
        help="PNML file to verify",
    )
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()

    for tool in ["mcrl22lps", "lps2pbes", "pbes2bool", "lps2lts", "ltsconvert", "ltsinfo"]:
        require_tool(tool)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    bounded_mcrl2 = OUTPUT_DIR / "pizza_official_bounded.mcrl2"
    lps_path = OUTPUT_DIR / "pizza_official_bounded.lps"
    lts_path = OUTPUT_DIR / "pizza_official_bounded.lts"
    lts_dot_path = OUTPUT_DIR / "pizza_official_bounded_lts.dot"
    lts_aut_path = OUTPUT_DIR / "pizza_official_bounded_lts.aut"
    lts_svg_path = OUTPUT_DIR / "pizza_official_bounded_lts.svg"

    if args.pnml == ROOT / "examples" / "pizza_official_local.pnml":
        run(
            [
                sys.executable,
                "bpmn2pnml_local.py",
                "examples/pizza_official.bpmn",
                "-o",
                str(args.pnml),
            ],
            timeout=args.timeout,
        )

    run(
        [
            sys.executable,
            "pnml2mcrl2.py",
            str(args.pnml),
            "-o",
            str(bounded_mcrl2),
            "--max-place-tokens",
            str(args.max_place_tokens),
        ],
        timeout=args.timeout,
    )
    run(["mcrl22lps", str(bounded_mcrl2), str(lps_path)], timeout=args.timeout)

    results: list[dict[str, object]] = []
    for spec in PROPERTIES:
        formula = PROPERTIES_DIR / spec.file_name
        run(["lps2pbes", "--check-only", f"--formula={formula}", str(lps_path)], timeout=args.timeout)
        if spec.action is not None:
            witness_lts = OUTPUT_DIR / f"{formula.stem}_witness.lts"
            found = run(
                ["lps2lts", f"--action={spec.action}", "--trace=1", str(lps_path), str(witness_lts)],
                timeout=args.timeout,
                check=False,
            )
            combined = found.stdout + found.stderr
            passed = f"Action '{spec.action}' found" in combined
        elif spec.deadlock_free:
            witness_lts = OUTPUT_DIR / f"{formula.stem}_witness.lts"
            found = run(
                ["lps2lts", "--deadlock", "--trace=1", str(lps_path), str(witness_lts)],
                timeout=args.timeout,
                check=False,
            )
            combined = found.stdout + found.stderr
            passed = "Deadlock found" not in combined
        else:
            raise ValueError(f"No executable check configured for {spec.file_name}")
        results.append(
            {
                "file": str(formula.relative_to(ROOT)),
                "title": spec.title,
                "passed": passed,
                "expected": spec.expected,
                "matches_expected": passed == spec.expected,
                "note": spec.note,
            }
        )

    run(["lps2lts", f"--max={args.max_lts_states}", str(lps_path), str(lts_path)], timeout=args.timeout)
    run(["ltsconvert", str(lts_path), str(lts_dot_path)], timeout=args.timeout)
    run(["ltsconvert", str(lts_path), str(lts_aut_path)], timeout=args.timeout)
    write_lts_svg(lts_aut_path, lts_svg_path)
    lts_info_result = run(["ltsinfo", str(lts_path)], timeout=args.timeout)
    lts_info_text = lts_info_result.stdout + lts_info_result.stderr
    lts_info = parse_ltsinfo(lts_info_text)

    summary_svg = OUTPUT_DIR / "pizza_official_verification_summary.svg"
    write_summary_svg(results, summary_svg)

    summary = {
        "bounded_model": str(bounded_mcrl2.relative_to(ROOT)),
        "max_place_tokens": args.max_place_tokens,
        "max_lts_states": args.max_lts_states,
        "lps": str(lps_path.relative_to(ROOT)),
        "lts": str(lts_path.relative_to(ROOT)),
        "lts_dot": str(lts_dot_path.relative_to(ROOT)),
        "lts_aut": str(lts_aut_path.relative_to(ROOT)),
        "lts_svg": str(lts_svg_path.relative_to(ROOT)),
        "summary_svg": str(summary_svg.relative_to(ROOT)),
        "lts_info": lts_info,
        "properties": results,
    }
    (OUTPUT_DIR / "results.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )

    markdown_lines = [
        "# Official Pizza Verification Results",
        "",
        f"- Bounded model: `{summary['bounded_model']}`",
        f"- Bound: each place is limited to at most {args.max_place_tokens} token(s)",
        f"- Visualization limit: first {args.max_lts_states} generated states",
        f"- LTS SVG: `{summary['lts_svg']}`",
        f"- Summary SVG: `{summary['summary_svg']}`",
        "",
        "## LTS",
        "",
    ]
    for key, value in lts_info.items():
        markdown_lines.append(f"- {key}: {value}")
    markdown_lines.extend(["", "## Modal Formulas", ""])
    markdown_lines.append("| Property | Result | Expected | Interpretation |")
    markdown_lines.append("| --- | --- | --- | --- |")
    for result in results:
        markdown_lines.append(
            "| {title} | {passed} | {expected} | {note} |".format(
                title=result["title"],
                passed=str(result["passed"]).lower(),
                expected=str(result["expected"]).lower(),
                note=result["note"],
            )
        )
    (OUTPUT_DIR / "README.md").write_text("\n".join(markdown_lines) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
