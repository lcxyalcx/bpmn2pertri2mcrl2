#!/usr/bin/env python3
"""Convert PNML (Petri Net) to mCRL2."""

from __future__ import annotations

import argparse
import dataclasses
import pathlib
import re
import xml.etree.ElementTree as ET


@dataclasses.dataclass(frozen=True)
class Place:
    pid: str
    name: str
    tokens: int


@dataclasses.dataclass(frozen=True)
class Transition:
    tid: str
    name: str


@dataclasses.dataclass(frozen=True)
class Arc:
    source: str
    target: str


@dataclasses.dataclass
class Net:
    places: dict[str, Place]
    transitions: dict[str, Transition]
    arcs: list[Arc]


def _strip_namespace(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _read_text(element: ET.Element | None) -> str:
    if element is None or element.text is None:
        return ""
    return element.text.strip()


def _parse_initial_marking(place: ET.Element) -> int:
    for child in place.iter():
        if _strip_namespace(child.tag) == "initialMarking":
            text_node = child.find(".//")
            return int(_read_text(text_node) or 0)
    return 0


def parse_pnml(path: pathlib.Path) -> Net:
    tree = ET.parse(path)
    root = tree.getroot()

    places: dict[str, Place] = {}
    transitions: dict[str, Transition] = {}
    arcs: list[Arc] = []

    for elem in root.iter():
        tag = _strip_namespace(elem.tag)
        if tag == "place":
            pid = elem.attrib.get("id", "")
            name_text = _read_text(elem.find(".//{*}name/{*}text"))
            tokens = _parse_initial_marking(elem)
            if pid:
                places[pid] = Place(pid=pid, name=name_text or pid, tokens=tokens)
        elif tag == "transition":
            tid = elem.attrib.get("id", "")
            name_text = _read_text(elem.find(".//{*}name/{*}text"))
            if tid:
                transitions[tid] = Transition(tid=tid, name=name_text or tid)
        elif tag == "arc":
            source = elem.attrib.get("source", "")
            target = elem.attrib.get("target", "")
            if source and target:
                arcs.append(Arc(source=source, target=target))

    return Net(places=places, transitions=transitions, arcs=arcs)


def _sanitize_identifier(value: str) -> str:
    value = value.strip()
    value = re.sub(r"[^A-Za-z0-9_]", "_", value)
    value = re.sub(r"_+", "_", value)
    if not value:
        value = "x"
    if value[0].isdigit():
        value = f"x_{value}"
    return value


def _build_place_mapping(net: Net) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for index, pid in enumerate(sorted(net.places.keys())):
        mapping[pid] = f"p_{index}"
    return mapping


def _build_transition_mapping(net: Net) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for index, tid in enumerate(sorted(net.transitions.keys())):
        mapping[tid] = f"t_{index}"
    return mapping


def _collect_pre_post(net: Net) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    pre: dict[str, list[str]] = {tid: [] for tid in net.transitions}
    post: dict[str, list[str]] = {tid: [] for tid in net.transitions}

    for arc in net.arcs:
        if arc.target in net.transitions and arc.source in net.places:
            pre[arc.target].append(arc.source)
        elif arc.source in net.transitions and arc.target in net.places:
            post[arc.source].append(arc.target)

    return pre, post


def _guard_expression(place_ids: list[str], place_map: dict[str, str]) -> str:
    if not place_ids:
        return "true"
    guard_parts = [f"m({place_map[pid]}) > 0" for pid in place_ids]
    return " && ".join(guard_parts)


def _update_expression(
    place_map: dict[str, str],
    pre_places: list[str],
    post_places: list[str],
) -> str:
    updates = {pid: 0 for pid in place_map}
    for pid in pre_places:
        updates[pid] -= 1
    for pid in post_places:
        updates[pid] += 1

    def build_case(items: list[str]) -> str:
        if not items:
            return "m(p)"
        pid = items[0]
        delta = updates[pid]
        target = place_map[pid]
        if delta > 0:
            expr = f"m({target}) + {delta}"
        elif delta < 0:
            expr = f"m({target}) - {abs(delta)}"
        else:
            expr = f"m({target})"
        rest = build_case(items[1:])
        return f"if(p == {target}, {expr}, {rest})"

    ordered_places = list(place_map.keys())
    return f"lambda p: Place . {build_case(ordered_places)}"


def generate_mcrl2(net: Net) -> str:
    place_map = _build_place_mapping(net)
    transition_map = _build_transition_mapping(net)
    pre, post = _collect_pre_post(net)

    place_lines = []
    for pid, alias in place_map.items():
        place = net.places[pid]
        place_lines.append(f"  {alias} /* {place.name} ({place.pid}) */")

    place_sort = " |\n".join(place_lines)

    init_lines = [f"init({alias}) = {net.places[pid].tokens};" for pid, alias in place_map.items()]

    act_lines = [f"fire_{transition_map[tid]}" for tid in transition_map]

    update_lines: list[str] = []
    for tid, alias in transition_map.items():
        update_lines.append(
            "eqn update_{alias}(m) = {expr};".format(
                alias=alias,
                expr=_update_expression(place_map, pre[tid], post[tid]),
            )
        )

    proc_lines: list[str] = []
    for tid, alias in transition_map.items():
        guard = _guard_expression(pre[tid], place_map)
        proc_lines.append(
            f"({guard}) -> fire_{alias} . P(update_{alias}(m))"
        )

    proc_body = " +\n  ".join(proc_lines) if proc_lines else "delta"

    lines = [
        "% Auto-generated by pnml2mcrl2.py",
        "sort Place = struct",
        place_sort + ";",
        "sort Marking = Place -> Nat;",
        "map init : Marking;",
        "eqn",
        "  " + "\n  ".join(init_lines),
        "map",  # map block for update functions
        "  " + "\n  ".join([f"update_{alias}: Marking -> Marking" for alias in transition_map.values()]) + ";",
        "eqn",
        "  " + "\n  ".join(update_lines),
        "act",
        "  " + ", ".join(act_lines) + ";",
        "proc",
        "  P(m: Marking) =",
        "  " + proc_body + ";",
        "init P(init);",
        "",
    ]

    return "\n".join(lines)


def convert_file(input_path: pathlib.Path, output_path: pathlib.Path) -> None:
    net = parse_pnml(input_path)
    if not net.places:
        raise ValueError("No places found in PNML")
    if not net.transitions:
        raise ValueError("No transitions found in PNML")
    output_path.write_text(generate_mcrl2(net), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert PNML to mCRL2")
    parser.add_argument("input", type=pathlib.Path, help="Path to PNML file")
    parser.add_argument(
        "-o",
        "--output",
        type=pathlib.Path,
        help="Output mCRL2 file (default: input name with .mcrl2)",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    output = args.output
    if output is None:
        output = args.input.with_suffix(".mcrl2")
    convert_file(args.input, output)


if __name__ == "__main__":
    main()
