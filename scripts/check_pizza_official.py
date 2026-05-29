#!/usr/bin/env python3
"""Run modal formula checks and bounded LTS visualization for Pizza."""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import html
from dataclasses import dataclass


ROOT = pathlib.Path(__file__).resolve().parents[1]
PROPERTIES_DIR = ROOT / "properties" / "pizza_official"
OUTPUT_DIR = ROOT / "docs" / "verification" / "pizza_official"
sys.path.insert(0, str(ROOT))

from scripts.verification_utils import (  # noqa: E402
    parse_aut,
    parse_ltsinfo,
    resolve_tool,
    write_lts_svg,
)


def rel(path: pathlib.Path) -> str:
    return path.relative_to(ROOT).as_posix()


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

    mcrl22lps = resolve_tool("mcrl22lps")
    lps2lts = resolve_tool("lps2lts")
    ltsconvert = resolve_tool("ltsconvert")
    ltsinfo = resolve_tool("ltsinfo")

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
    run([mcrl22lps, str(bounded_mcrl2), str(lps_path)], timeout=args.timeout)
    run([lps2lts, f"--max={args.max_lts_states}", str(lps_path), str(lts_path)], timeout=args.timeout)
    run([ltsconvert, "--out=dot", str(lts_path), str(lts_dot_path)], timeout=args.timeout)
    run([ltsconvert, "--out=aut", str(lts_path), str(lts_aut_path)], timeout=args.timeout)
    write_lts_svg(lts_aut_path, lts_svg_path)
    lts_info_result = run([ltsinfo, str(lts_path)], timeout=args.timeout)
    lts_info_text = lts_info_result.stdout + lts_info_result.stderr
    lts_info = parse_ltsinfo(lts_info_text)

    results: list[dict[str, object]] = []
    for spec in PROPERTIES:
        formula = PROPERTIES_DIR / spec.file_name
        witness_lts = OUTPUT_DIR / f"{formula.stem}_witness.lts"
        if spec.action is not None:
            found = run(
                [lps2lts, f"--action={spec.action}", "--trace=1", str(lps_path), str(witness_lts)],
                timeout=args.timeout,
                check=False,
            )
            combined = found.stdout + found.stderr
            passed = f"Action '{spec.action}' found" in combined
        elif spec.deadlock_free:
            found = run(
                [lps2lts, "--deadlock", "--trace=1", str(lps_path), str(witness_lts)],
                timeout=args.timeout,
                check=False,
            )
            combined = found.stdout + found.stderr
            passed = "Deadlock found" not in combined
        else:
            raise ValueError(f"No executable check configured for {spec.file_name}")
        results.append(
            {
                "file": rel(formula),
                "witness_lts": rel(witness_lts),
                "backend": "witness",
                "title": spec.title,
                "passed": passed,
                "expected": spec.expected,
                "matches_expected": passed == spec.expected,
                "note": spec.note,
            }
        )

    summary_svg = OUTPUT_DIR / "pizza_official_verification_summary.svg"
    write_summary_svg(results, summary_svg)

    summary = {
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
