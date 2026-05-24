#!/usr/bin/env python3
"""Redownload the official Pizza BPMN sample and regenerate conversion visuals."""

from __future__ import annotations

import html
import json
import pathlib
import re
import shutil
import subprocess
import sys
import textwrap


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent
RUN_DIR = ROOT / "docs" / "runs" / "pizza_official_redownload_20260518"
SOURCE_PAGE = "https://maude.lcc.uma.es/BPMN-R/pizza/"
SOURCE_BPMN = SOURCE_PAGE + "files/triso%20-%20Order%20Process%20for%20Pizza%20V4.bpmn"
SOURCE_BPMN_WITH_COMMENTS = SOURCE_PAGE + "files/pizza-with-comments.bpmn"
SOURCE_IMAGE = SOURCE_PAGE + "images/pizza-with-comments.png"

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS_DIR))

from bpmn2pnml_local import convert_file as convert_bpmn_to_pnml  # noqa: E402
from bpmn2pnml_local import parse_bpmn  # noqa: E402
from pnml2mcrl2 import generate_mcrl2, parse_pnml  # noqa: E402
from check_pizza_official import parse_aut, parse_ltsinfo, write_lts_svg  # noqa: E402


def run(cmd: list[str], cwd: pathlib.Path = ROOT, timeout: int = 240) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
        timeout=timeout,
    )


def require_tool(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise RuntimeError(f"Required tool not found on PATH: {name}")
    return path


def download(url: str, output: pathlib.Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    run(["curl", "-L", "--fail", "--silent", "--show-error", url, "-o", str(output)])


def bpmn_stats(bpmn_path: pathlib.Path) -> dict[str, object]:
    model = parse_bpmn(bpmn_path)
    tag_counts: dict[str, int] = {}
    for node in model.nodes.values():
        tag_counts[node.tag] = tag_counts.get(node.tag, 0) + 1
    return {
        "processes": len(model.process_ids),
        "nodes": len(model.nodes),
        "sequence_flows": len(model.sequence_flows),
        "message_flows": len(model.message_flows),
        "tag_counts": tag_counts,
    }


def pnml_stats(pnml_path: pathlib.Path) -> tuple[dict[str, object], dict[str, list[str]], dict[str, list[str]]]:
    net = parse_pnml(pnml_path)
    pre: dict[str, list[str]] = {tid: [] for tid in net.transitions}
    post: dict[str, list[str]] = {tid: [] for tid in net.transitions}
    for arc in net.arcs:
        if arc.target in net.transitions and arc.source in net.places:
            pre[arc.target].append(arc.source)
        elif arc.source in net.transitions and arc.target in net.places:
            post[arc.source].append(arc.target)
    stats = {
        "places": len(net.places),
        "transitions": len(net.transitions),
        "arcs": len(net.arcs),
        "initial_places": [place.name for place in net.places.values() if place.tokens > 0],
    }
    return stats, pre, post


def mcrl2_stats(mcrl2_path: pathlib.Path) -> dict[str, object]:
    text = mcrl2_path.read_text(encoding="utf-8")
    place_count = len(re.findall(r"^%   p_\d+ =", text, flags=re.MULTILINE))
    transition_lines = re.findall(r"^%   t_\d+/([A-Za-z0-9_]+) =", text, flags=re.MULTILINE)
    actions_line = re.search(r"^act\s+(.+?);$", text, flags=re.MULTILINE | re.DOTALL)
    action_count = 0
    if actions_line:
        action_count = len([part.strip() for part in actions_line.group(1).split(",") if part.strip()])
    return {
        "places": place_count,
        "actions": action_count,
        "sample_actions": transition_lines[:8],
    }


def write_pipeline_svg(output: pathlib.Path, files: dict[str, pathlib.Path]) -> None:
    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1180" height="230" viewBox="0 0 1180 230">
  <defs>
    <marker id="arrow" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">
      <path d="M0,0 L10,4 L0,8 z" fill="#334155"/>
    </marker>
  </defs>
  <rect width="100%" height="100%" fill="#ffffff"/>
  <text x="36" y="38" font-family="Helvetica" font-size="24" font-weight="700" fill="#0f172a">Pizza official rerun pipeline</text>
  <text x="36" y="64" font-family="Helvetica" font-size="13" fill="#475569">Downloaded from the official BPMN-R Pizza example page, then converted locally.</text>

  <rect x="40" y="95" width="220" height="88" rx="12" fill="#dbeafe" stroke="#2563eb" stroke-width="2"/>
  <text x="150" y="124" text-anchor="middle" font-family="Helvetica" font-size="16" font-weight="700" fill="#1d4ed8">1. BPMN</text>
  <text x="150" y="148" text-anchor="middle" font-family="Helvetica" font-size="12" fill="#334155">{html.escape(files["bpmn"].name)}</text>
  <text x="150" y="166" text-anchor="middle" font-family="Helvetica" font-size="11" fill="#64748b">official download</text>

  <rect x="335" y="95" width="220" height="88" rx="12" fill="#dcfce7" stroke="#16a34a" stroke-width="2"/>
  <text x="445" y="124" text-anchor="middle" font-family="Helvetica" font-size="16" font-weight="700" fill="#166534">2. PNML</text>
  <text x="445" y="148" text-anchor="middle" font-family="Helvetica" font-size="12" fill="#334155">{html.escape(files["pnml"].name)}</text>
  <text x="445" y="166" text-anchor="middle" font-family="Helvetica" font-size="11" fill="#64748b">bpmn2pnml_local.py</text>

  <rect x="630" y="95" width="220" height="88" rx="12" fill="#fef3c7" stroke="#d97706" stroke-width="2"/>
  <text x="740" y="124" text-anchor="middle" font-family="Helvetica" font-size="16" font-weight="700" fill="#92400e">3. mCRL2</text>
  <text x="740" y="148" text-anchor="middle" font-family="Helvetica" font-size="12" fill="#334155">{html.escape(files["mcrl2"].name)}</text>
  <text x="740" y="166" text-anchor="middle" font-family="Helvetica" font-size="11" fill="#64748b">pnml2mcrl2.py</text>

  <rect x="925" y="95" width="220" height="88" rx="12" fill="#fce7f3" stroke="#db2777" stroke-width="2"/>
  <text x="1035" y="124" text-anchor="middle" font-family="Helvetica" font-size="16" font-weight="700" fill="#be185d">4. Bounded LTS</text>
  <text x="1035" y="148" text-anchor="middle" font-family="Helvetica" font-size="12" fill="#334155">{html.escape(files["lts_svg"].name)}</text>
  <text x="1035" y="166" text-anchor="middle" font-family="Helvetica" font-size="11" fill="#64748b">mcrl22lps + lps2lts</text>

  <line x1="260" y1="139" x2="335" y2="139" stroke="#334155" stroke-width="2" marker-end="url(#arrow)"/>
  <line x1="555" y1="139" x2="630" y2="139" stroke="#334155" stroke-width="2" marker-end="url(#arrow)"/>
  <line x1="850" y1="139" x2="925" y2="139" stroke="#334155" stroke-width="2" marker-end="url(#arrow)"/>
</svg>
"""
    output.write_text(svg, encoding="utf-8")


def write_bpmn_summary_svg(output: pathlib.Path, stats: dict[str, object], source_image_name: str) -> None:
    tags = stats["tag_counts"]
    rows = [
        ("Processes", str(stats["processes"])),
        ("Flow nodes", str(stats["nodes"])),
        ("Sequence flows", str(stats["sequence_flows"])),
        ("Message flows", str(stats["message_flows"])),
        ("Tasks", str(tags.get("task", 0))),
        ("Parallel gateways", str(tags.get("parallelGateway", 0))),
        ("Event-based gateways", str(tags.get("eventBasedGateway", 0))),
        ("Catch events", str(tags.get("intermediateCatchEvent", 0))),
    ]
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="900" height="420" viewBox="0 0 900 420">',
        '  <rect width="100%" height="100%" fill="#ffffff"/>',
        '  <text x="32" y="40" font-family="Helvetica" font-size="24" font-weight="700" fill="#0f172a">BPMN source summary</text>',
        '  <text x="32" y="66" font-family="Helvetica" font-size="13" fill="#475569">Official Pizza example downloaded from BPMN-R.</text>',
        '  <rect x="32" y="96" width="836" height="290" rx="14" fill="#eff6ff" stroke="#93c5fd"/>',
        '  <text x="56" y="128" font-family="Helvetica" font-size="16" font-weight="700" fill="#1d4ed8">Source asset</text>',
        f'  <text x="56" y="152" font-family="Helvetica" font-size="13" fill="#334155">{html.escape(source_image_name)}</text>',
    ]
    y = 190
    for key, value in rows:
        lines.append(f'  <text x="56" y="{y}" font-family="Helvetica" font-size="14" fill="#0f172a">{html.escape(key)}</text>')
        lines.append(f'  <text x="300" y="{y}" font-family="Helvetica" font-size="14" fill="#334155">{html.escape(value)}</text>')
        y += 28
    lines.extend(
        [
            '  <text x="480" y="128" font-family="Helvetica" font-size="16" font-weight="700" fill="#1d4ed8">Why this matters</text>',
            '  <text x="480" y="156" font-family="Helvetica" font-size="13" fill="#334155">This is the collaboration-level BPMN with two participants, message flows, timers,</text>',
            '  <text x="480" y="176" font-family="Helvetica" font-size="13" fill="#334155">event-based choice, and the ask/calm customer loop that makes Pizza interesting.</text>',
        ]
    )
    lines.append("</svg>")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_pnml_svg(
    output: pathlib.Path,
    pnml_path: pathlib.Path,
    stats: dict[str, object],
    pre: dict[str, list[str]],
    post: dict[str, list[str]],
) -> None:
    net = parse_pnml(pnml_path)
    place_ids = sorted(net.places.keys())
    transition_ids = sorted(net.transitions.keys())
    left_x = 165
    right_x = 640
    place_y0 = 110
    transition_y0 = 100
    place_gap = 28
    transition_gap = 32
    width = 1060
    height = max(940, 170 + max(len(place_ids) * place_gap, len(transition_ids) * transition_gap))

    coords_place = {
        pid: (left_x, place_y0 + index * place_gap) for index, pid in enumerate(place_ids)
    }
    coords_transition = {
        tid: (right_x, transition_y0 + index * transition_gap)
        for index, tid in enumerate(transition_ids)
    }

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '  <defs><marker id="arrow" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto"><path d="M0,0 L10,4 L0,8 z" fill="#94a3b8"/></marker></defs>',
        '  <rect width="100%" height="100%" fill="#ffffff"/>',
        '  <text x="28" y="38" font-family="Helvetica" font-size="24" font-weight="700" fill="#0f172a">PNML overview</text>',
        f'  <text x="28" y="64" font-family="Helvetica" font-size="13" fill="#475569">{stats["places"]} places, {stats["transitions"]} transitions, {stats["arcs"]} arcs</text>',
        '  <text x="94" y="92" font-family="Helvetica" font-size="13" fill="#92400e">Places</text>',
        '  <text x="605" y="92" font-family="Helvetica" font-size="13" fill="#1d4ed8">Transitions</text>',
    ]

    for tid, place_list in pre.items():
        x2, y2 = coords_transition[tid]
        for pid in place_list:
            x1, y1 = coords_place[pid]
            lines.append(
                f'  <line x1="{x1 + 26}" y1="{y1}" x2="{x2 - 55}" y2="{y2}" stroke="#cbd5e1" stroke-width="1.1" marker-end="url(#arrow)"/>'
            )
    for tid, place_list in post.items():
        x1, y1 = coords_transition[tid]
        for pid in place_list:
            x2, y2 = coords_place[pid]
            lines.append(
                f'  <line x1="{x1 + 55}" y1="{y1}" x2="{x2 - 26}" y2="{y2}" stroke="#cbd5e1" stroke-width="1.1" marker-end="url(#arrow)"/>'
            )

    for pid in place_ids:
        place = net.places[pid]
        x, y = coords_place[pid]
        fill = "#fef3c7" if place.tokens > 0 else "#fff7ed"
        stroke = "#d97706"
        lines.extend(
            [
                f'  <circle cx="{x}" cy="{y}" r="18" fill="{fill}" stroke="{stroke}" stroke-width="1.4"/>',
                f'  <text x="{x + 32}" y="{y + 4}" font-family="Helvetica" font-size="10" fill="#334155">{html.escape(place.name[:42])}</text>',
            ]
        )
        if place.tokens > 0:
            lines.append(
                f'  <text x="{x}" y="{y + 4}" text-anchor="middle" font-family="Helvetica" font-size="11" font-weight="700" fill="#92400e">{place.tokens}</text>'
            )

    for tid in transition_ids:
        transition = net.transitions[tid]
        x, y = coords_transition[tid]
        lines.extend(
            [
                f'  <rect x="{x - 48}" y="{y - 14}" width="96" height="28" rx="5" fill="#dbeafe" stroke="#2563eb" stroke-width="1.3"/>',
                f'  <text x="{x}" y="{y + 4}" text-anchor="middle" font-family="Helvetica" font-size="9.5" fill="#1d4ed8">{html.escape(transition.name[:28])}</text>',
            ]
        )

    lines.append("</svg>")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_mcrl2_svg(output: pathlib.Path, stats: dict[str, object], sample_actions: list[str]) -> None:
    action_rows = sample_actions[:8]
    height = 300 + len(action_rows) * 24
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="960" height="{height}" viewBox="0 0 960 {height}">',
        '  <rect width="100%" height="100%" fill="#ffffff"/>',
        '  <text x="32" y="40" font-family="Helvetica" font-size="24" font-weight="700" fill="#0f172a">mCRL2 model summary</text>',
        '  <text x="32" y="66" font-family="Helvetica" font-size="13" fill="#475569">The PNML net is encoded as a marking-transition process.</text>',
        '  <rect x="32" y="98" width="250" height="130" rx="12" fill="#eff6ff" stroke="#60a5fa"/>',
        '  <text x="56" y="128" font-family="Helvetica" font-size="16" font-weight="700" fill="#1d4ed8">Sorts and state</text>',
        f'  <text x="56" y="156" font-family="Helvetica" font-size="13" fill="#334155">Place aliases: {stats["places"]}</text>',
        '  <text x="56" y="178" font-family="Helvetica" font-size="13" fill="#334155">Marking = Place -&gt; Int</text>',
        '  <text x="56" y="200" font-family="Helvetica" font-size="13" fill="#334155">Initial marking comes from PNML initial tokens</text>',
        '  <rect x="322" y="98" width="250" height="130" rx="12" fill="#fef3c7" stroke="#f59e0b"/>',
        '  <text x="346" y="128" font-family="Helvetica" font-size="16" font-weight="700" fill="#92400e">Actions and guards</text>',
        f'  <text x="346" y="156" font-family="Helvetica" font-size="13" fill="#334155">Actions generated: {stats["actions"]}</text>',
        '  <text x="346" y="178" font-family="Helvetica" font-size="13" fill="#334155">Each transition becomes one action with an enabling guard</text>',
        '  <text x="346" y="200" font-family="Helvetica" font-size="13" fill="#334155">Enabled iff all input places contain tokens</text>',
        '  <rect x="612" y="98" width="316" height="130" rx="12" fill="#dcfce7" stroke="#22c55e"/>',
        '  <text x="636" y="128" font-family="Helvetica" font-size="16" font-weight="700" fill="#166534">Update style</text>',
        '  <text x="636" y="156" font-family="Helvetica" font-size="13" fill="#334155">update_t(m) decrements pre-places and increments post-places</text>',
        '  <text x="636" y="178" font-family="Helvetica" font-size="13" fill="#334155">proc P(m) = guard -&gt; action . P(update_t(m)) + ...</text>',
        '  <text x="636" y="200" font-family="Helvetica" font-size="13" fill="#334155">Bounded LTS view uses max-place-tokens=1</text>',
        '  <text x="32" y="268" font-family="Helvetica" font-size="16" font-weight="700" fill="#0f172a">Sample semantic actions</text>',
    ]
    y = 296
    for action in action_rows:
        lines.append(f'  <text x="56" y="{y}" font-family="Helvetica" font-size="13" fill="#334155">{html.escape(action)}</text>')
        y += 24
    lines.append("</svg>")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_report(
    output: pathlib.Path,
    summary: dict[str, object],
    files: dict[str, pathlib.Path],
) -> None:
    report = f"""# Pizza 官方样例重新转换报告

本次运行直接从官方页面重新下载 Pizza BPMN 样例，再在本地重新执行：

`BPMN -> PNML -> mCRL2 -> bounded LTS`

## 官方来源

- 页面：[{SOURCE_PAGE}]({SOURCE_PAGE})
- 原始 BPMN：[{SOURCE_BPMN}]({SOURCE_BPMN})
- 带注释 BPMN：[{SOURCE_BPMN_WITH_COMMENTS}]({SOURCE_BPMN_WITH_COMMENTS})

## 本次运行产物

- BPMN：`{files["bpmn"].relative_to(ROOT)}`
- 带注释 BPMN：`{files["bpmn_comments"].relative_to(ROOT)}`
- 官方示意图：`{files["bpmn_png"].relative_to(ROOT)}`
- PNML：`{files["pnml"].relative_to(ROOT)}`
- mCRL2：`{files["mcrl2"].relative_to(ROOT)}`
- bounded mCRL2：`{files["bounded_mcrl2"].relative_to(ROOT)}`
- LPS：`{files["lps"].relative_to(ROOT)}`
- LTS：`{files["lts"].relative_to(ROOT)}`
- AUT：`{files["aut"].relative_to(ROOT)}`

## 统计

- BPMN：{summary["bpmn"]["processes"]} 个 process，{summary["bpmn"]["nodes"]} 个 flow node，{summary["bpmn"]["message_flows"]} 条 message flow
- PNML：{summary["pnml"]["places"]} 个 place，{summary["pnml"]["transitions"]} 个 transition，{summary["pnml"]["arcs"]} 条 arc
- mCRL2：{summary["mcrl2"]["places"]} 个 place alias，{summary["mcrl2"]["actions"]} 个 action
- bounded LTS：{summary["lts"]["states"]} 个状态，{summary["lts"]["transitions"]} 条迁移

## 可视化

### 1. 流程总览

![pipeline]({files["pipeline_svg"].relative_to(ROOT)})

### 2. 官方 BPMN 输入概览

![bpmn-summary]({files["bpmn_summary_svg"].relative_to(ROOT)})

### 3. 官方页面中的 BPMN 图

![bpmn-image]({files["bpmn_png"].relative_to(ROOT)})

### 4. PNML 结构概览

![pnml-overview]({files["pnml_svg"].relative_to(ROOT)})

### 5. mCRL2 结构概览

![mcrl2-overview]({files["mcrl2_svg"].relative_to(ROOT)})

### 6. bounded LTS 可视化

![lts-overview]({files["lts_svg"].relative_to(ROOT)})
"""
    output.write_text(report, encoding="utf-8")


def main() -> None:
    for tool in ["curl", "mcrl22lps", "lps2lts", "ltsconvert", "ltsinfo"]:
        require_tool(tool)

    RUN_DIR.mkdir(parents=True, exist_ok=True)
    bpmn_path = RUN_DIR / "pizza_official_downloaded.bpmn"
    bpmn_comments_path = RUN_DIR / "pizza_official_with_comments_downloaded.bpmn"
    bpmn_png_path = RUN_DIR / "pizza_official_source.png"
    pnml_path = RUN_DIR / "pizza_official_downloaded_local.pnml"
    mcrl2_path = RUN_DIR / "pizza_official_downloaded_local.mcrl2"
    bounded_mcrl2_path = RUN_DIR / "pizza_official_downloaded_bounded.mcrl2"
    lps_path = RUN_DIR / "pizza_official_downloaded_bounded.lps"
    lts_path = RUN_DIR / "pizza_official_downloaded_bounded.lts"
    aut_path = RUN_DIR / "pizza_official_downloaded_bounded.aut"
    dot_path = RUN_DIR / "pizza_official_downloaded_bounded.dot"
    lts_svg_path = RUN_DIR / "pizza_official_downloaded_bounded_lts.svg"
    pipeline_svg_path = RUN_DIR / "01_pipeline.svg"
    bpmn_summary_svg_path = RUN_DIR / "02_bpmn_summary.svg"
    pnml_svg_path = RUN_DIR / "03_pnml_overview.svg"
    mcrl2_svg_path = RUN_DIR / "04_mcrl2_summary.svg"
    report_path = RUN_DIR / "README.md"
    summary_json_path = RUN_DIR / "summary.json"

    download(SOURCE_BPMN, bpmn_path)
    download(SOURCE_BPMN_WITH_COMMENTS, bpmn_comments_path)
    download(SOURCE_IMAGE, bpmn_png_path)

    convert_bpmn_to_pnml(bpmn_path, pnml_path)
    net = parse_pnml(pnml_path)
    mcrl2_path.write_text(generate_mcrl2(net), encoding="utf-8")
    bounded_mcrl2_path.write_text(
        generate_mcrl2(net, max_place_tokens=1),
        encoding="utf-8",
    )

    run(["mcrl22lps", str(bounded_mcrl2_path), str(lps_path)])
    run(["lps2lts", "--cached", "--max=200", str(lps_path), str(lts_path)])
    run(["ltsconvert", str(lts_path), str(aut_path)])
    run(["ltsconvert", str(lts_path), str(dot_path)])
    ltsinfo_result = run(["ltsinfo", str(lts_path)])
    ltsinfo_output = ltsinfo_result.stdout + "\n" + ltsinfo_result.stderr
    write_lts_svg(aut_path, lts_svg_path)

    bpmn = bpmn_stats(bpmn_path)
    pnml, pre, post = pnml_stats(pnml_path)
    mcrl2 = mcrl2_stats(mcrl2_path)
    lts = parse_ltsinfo(ltsinfo_output)
    initial_state, _, transitions = parse_aut(aut_path)
    summary = {
        "source": {
            "page": SOURCE_PAGE,
            "bpmn": SOURCE_BPMN,
            "bpmn_with_comments": SOURCE_BPMN_WITH_COMMENTS,
            "image": SOURCE_IMAGE,
        },
        "bpmn": bpmn,
        "pnml": pnml,
        "mcrl2": mcrl2,
        "lts": {
            "initial_state": initial_state,
            "states": lts.get("Number of states", "unknown"),
            "transitions": lts.get("Number of transitions", str(len(transitions))),
            "aut_transitions": len(transitions),
        },
    }

    files = {
        "bpmn": bpmn_path,
        "bpmn_comments": bpmn_comments_path,
        "bpmn_png": bpmn_png_path,
        "pnml": pnml_path,
        "mcrl2": mcrl2_path,
        "bounded_mcrl2": bounded_mcrl2_path,
        "lps": lps_path,
        "lts": lts_path,
        "aut": aut_path,
        "lts_svg": lts_svg_path,
        "pipeline_svg": pipeline_svg_path,
        "bpmn_summary_svg": bpmn_summary_svg_path,
        "pnml_svg": pnml_svg_path,
        "mcrl2_svg": mcrl2_svg_path,
    }

    write_pipeline_svg(pipeline_svg_path, files)
    write_bpmn_summary_svg(bpmn_summary_svg_path, bpmn, bpmn_png_path.name)
    write_pnml_svg(pnml_svg_path, pnml_path, pnml, pre, post)
    write_mcrl2_svg(mcrl2_svg_path, mcrl2, mcrl2["sample_actions"])
    write_report(report_path, summary, files)
    summary_json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(textwrap.dedent(
        f"""
        Generated official Pizza rerun artifacts in:
          {RUN_DIR}
        Report:
          {report_path}
        """
    ).strip())


if __name__ == "__main__":
    main()
