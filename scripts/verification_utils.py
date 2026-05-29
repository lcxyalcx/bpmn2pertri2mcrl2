#!/usr/bin/env python3
"""Shared helpers for mCRL2 verification and LTS visualization."""

from __future__ import annotations

import html
import os
import pathlib
import re
import shutil
from collections import defaultdict, deque

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _tool_name_candidates(name: str) -> list[str]:
    if os.name == "nt" and not name.lower().endswith(".exe"):
        return [f"{name}.exe", name]
    return [name]


def _bundled_bin_dirs() -> list[pathlib.Path]:
    candidates: list[pathlib.Path] = []
    env_bin = os.environ.get("MCRL2_BIN")
    if env_bin:
        path = pathlib.Path(env_bin)
        if path.is_dir():
            candidates.append(path)

    tools_dir = ROOT / ".tools"
    if tools_dir.is_dir():
        for release_dir in sorted(tools_dir.glob("mcrl2-*"), reverse=True):
            candidates.extend(sorted(release_dir.rglob("bin"), reverse=True))

    unique: list[pathlib.Path] = []
    seen: set[pathlib.Path] = set()
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen or not resolved.is_dir():
            continue
        seen.add(resolved)
        unique.append(resolved)
    return unique


def resolve_tool(name: str) -> str:
    direct = shutil.which(name)
    if direct is not None:
        return direct

    for bin_dir in _bundled_bin_dirs():
        for candidate in _tool_name_candidates(name):
            path = bin_dir / candidate
            if path.is_file():
                return str(path)

    raise RuntimeError(f"Required tool not found on PATH or in bundled .tools: {name}")


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


def parse_ltsinfo(output: str) -> dict[str, str]:
    info: dict[str, str] = {}
    for line in output.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            info[key.strip()] = value.strip().rstrip(".")
        elif line.strip():
            info[line.strip().rstrip(".")] = "yes"
    return info


def parse_bool_result(output: str) -> bool:
    exact = re.findall(r"(?im)^\s*(true|false)\s*$", output)
    if exact:
        return exact[-1].lower() == "true"

    tokens = re.findall(r"\b(true|false)\b", output, flags=re.IGNORECASE)
    if tokens:
        return tokens[-1].lower() == "true"

    raise ValueError(f"Cannot parse boolean solver result from output: {output!r}")


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
        start_y = margin_y + max(0, (max_level_size - len(states)) * y_gap // 2)
        for index, state in enumerate(states):
            coords[state] = (margin_x + d * x_gap, start_y + index * y_gap)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<defs><marker id="arrow" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto"><path d="M0,0 L10,4 L0,8 z" fill="#64748b"/></marker></defs>',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="28" y="34" font-family="Helvetica" font-size="22" font-weight="700">Bounded LTS</text>',
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
