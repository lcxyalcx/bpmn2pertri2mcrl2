#!/usr/bin/env python3
"""Convert a practical BPMN collaboration subset to PNML.

The converter is intentionally conservative and targets the official Pizza
example shape: sequence flows become places, flow nodes become transitions, and
gating message flows become places consumed by message/start/catch receivers.
Informational task-to-task message flows are omitted to avoid artificial
request/response cycles in the Petri net.
"""

from __future__ import annotations

import argparse
import dataclasses
import pathlib
import re
import xml.etree.ElementTree as ET


@dataclasses.dataclass(frozen=True)
class BpmnNode:
    nid: str
    tag: str
    name: str
    process_id: str | None


@dataclasses.dataclass(frozen=True)
class Flow:
    fid: str
    name: str
    source: str
    target: str


@dataclasses.dataclass
class BpmnModel:
    nodes: dict[str, BpmnNode]
    process_ids: list[str]
    sequence_flows: dict[str, Flow]
    message_flows: dict[str, Flow]


@dataclasses.dataclass(frozen=True)
class Place:
    pid: str
    name: str
    tokens: int = 0


@dataclasses.dataclass(frozen=True)
class Transition:
    tid: str
    name: str


@dataclasses.dataclass(frozen=True)
class Arc:
    aid: str
    source: str
    target: str


@dataclasses.dataclass
class PetriNet:
    places: dict[str, Place]
    transitions: dict[str, Transition]
    arcs: list[Arc]


FLOW_NODE_TAGS = {
    "startEvent",
    "endEvent",
    "task",
    "intermediateCatchEvent",
    "parallelGateway",
    "eventBasedGateway",
}


def _strip_namespace(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _read_xml_text(path: pathlib.Path) -> str:
    raw = path.read_bytes()
    head = raw[:200].decode("ascii", errors="ignore")
    match = re.search(r'encoding=["\']([^"\']+)["\']', head, flags=re.IGNORECASE)
    encoding = match.group(1) if match else "utf-8"
    return raw.decode(encoding)


def _safe_id(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_]", "_", value.strip())
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "x"


def _display_name(node: BpmnNode) -> str:
    if node.name:
        return node.name
    if node.tag == "parallelGateway":
        return f"parallel gateway {node.nid}"
    if node.tag == "eventBasedGateway":
        return f"event gateway {node.nid}"
    if node.tag == "endEvent":
        return "End"
    return node.nid


def parse_bpmn(path: pathlib.Path) -> BpmnModel:
    root = ET.fromstring(_read_xml_text(path))
    nodes: dict[str, BpmnNode] = {}
    process_ids: list[str] = []
    sequence_flows: dict[str, Flow] = {}
    message_flows: dict[str, Flow] = {}

    for process in root.iter():
        if _strip_namespace(process.tag) != "process":
            continue
        process_id = process.attrib.get("id", "")
        if process_id:
            process_ids.append(process_id)
        for child in process:
            tag = _strip_namespace(child.tag)
            if tag in FLOW_NODE_TAGS:
                nid = child.attrib.get("id", "")
                if nid:
                    nodes[nid] = BpmnNode(
                        nid=nid,
                        tag=tag,
                        name=child.attrib.get("name", "").strip(),
                        process_id=process_id,
                    )
            elif tag == "sequenceFlow":
                fid = child.attrib.get("id", "")
                source = child.attrib.get("sourceRef", "")
                target = child.attrib.get("targetRef", "")
                if fid and source and target:
                    sequence_flows[fid] = Flow(
                        fid=fid,
                        name=child.attrib.get("name", "").strip() or fid,
                        source=source,
                        target=target,
                    )

    for elem in root.iter():
        if _strip_namespace(elem.tag) != "messageFlow":
            continue
        fid = elem.attrib.get("id", "")
        source = elem.attrib.get("sourceRef", "")
        target = elem.attrib.get("targetRef", "")
        if fid and source and target:
            message_flows[fid] = Flow(
                fid=fid,
                name=elem.attrib.get("name", "").strip() or fid,
                source=source,
                target=target,
            )

    return BpmnModel(nodes, process_ids, sequence_flows, message_flows)


def _message_flow_gates_target(flow: Flow, model: BpmnModel) -> bool:
    target = model.nodes.get(flow.target)
    if target is None:
        return False
    if target.tag in {"startEvent", "intermediateCatchEvent"}:
        return True
    if target.tag == "task" and target.name.lower().startswith("receive"):
        return True
    return False


def _incoming_flows(flows: dict[str, Flow], node_id: str) -> list[Flow]:
    return [flow for flow in flows.values() if flow.target == node_id]


def _outgoing_flows(flows: dict[str, Flow], node_id: str) -> list[Flow]:
    return [flow for flow in flows.values() if flow.source == node_id]


def _add_arc(net: PetriNet, source: str, target: str) -> None:
    net.arcs.append(Arc(f"a_{len(net.arcs)}", source, target))


def _add_transition(
    net: PetriNet,
    tid: str,
    name: str,
    pre: list[str],
    post: list[str],
) -> None:
    net.transitions[tid] = Transition(tid, name)
    for place_id in pre:
        _add_arc(net, place_id, tid)
    for place_id in post:
        _add_arc(net, tid, place_id)


def convert_bpmn_to_pn(model: BpmnModel) -> PetriNet:
    net = PetriNet(places={}, transitions={}, arcs=[])
    gating_messages = {
        fid: flow
        for fid, flow in model.message_flows.items()
        if _message_flow_gates_target(flow, model)
    }

    for flow in model.sequence_flows.values():
        net.places[flow.fid] = Place(flow.fid, flow.name, 0)
    for flow in gating_messages.values():
        net.places[flow.fid] = Place(flow.fid, flow.name, 0)
    for process_id in model.process_ids:
        net.places[f"start_p_{_safe_id(process_id)}"] = Place(
            f"start_p_{_safe_id(process_id)}",
            f"Start {process_id}",
            0,
        )
        net.places[f"end_p_{_safe_id(process_id)}"] = Place(
            f"end_p_{_safe_id(process_id)}",
            f"End {process_id}",
            0,
        )

    for node in model.nodes.values():
        if node.tag == "startEvent" and not _incoming_flows(gating_messages, node.nid):
            start_id = f"start_p_{_safe_id(node.process_id or 'process')}"
            net.places[start_id] = dataclasses.replace(net.places[start_id], tokens=1)

    for node in model.nodes.values():
        incoming_seq = _incoming_flows(model.sequence_flows, node.nid)
        outgoing_seq = _outgoing_flows(model.sequence_flows, node.nid)
        incoming_msg = _incoming_flows(gating_messages, node.nid)
        outgoing_msg = _outgoing_flows(gating_messages, node.nid)
        incoming = [flow.fid for flow in incoming_seq]
        outgoing = [flow.fid for flow in outgoing_seq]

        if node.tag == "startEvent":
            pre = [flow.fid for flow in incoming_msg]
            if not pre:
                pre = [f"start_p_{_safe_id(node.process_id or 'process')}"]
            _add_transition(net, node.nid, _display_name(node), pre, outgoing)
        elif node.tag == "endEvent":
            end_id = f"end_p_{_safe_id(node.process_id or 'process')}"
            _add_transition(net, node.nid, _display_name(node), incoming, [end_id])
        elif node.tag == "eventBasedGateway":
            for incoming_flow in incoming_seq:
                for outgoing_flow in outgoing_seq:
                    tid = f"{node.nid}_from_{incoming_flow.fid}_to_{outgoing_flow.fid}"
                    _add_transition(
                        net,
                        tid,
                        f"choose {outgoing_flow.name}",
                        [incoming_flow.fid],
                        [outgoing_flow.fid],
                    )
        elif node.tag == "intermediateCatchEvent":
            message_inputs = [flow.fid for flow in incoming_msg]
            for flow in incoming_seq:
                tid = f"{node.nid}_from_{flow.fid}"
                _add_transition(
                    net,
                    tid,
                    _display_name(node),
                    [flow.fid, *message_inputs],
                    outgoing,
                )
        elif node.tag in {"task", "parallelGateway"}:
            pre = [*incoming, *[flow.fid for flow in incoming_msg]]
            post = [*outgoing, *[flow.fid for flow in outgoing_msg]]
            _add_transition(net, node.nid, _display_name(node), pre, post)

    process_end_places = [f"end_p_{_safe_id(pid)}" for pid in model.process_ids]
    if len(process_end_places) > 1:
        final_place = "end_p"
        net.places[final_place] = Place(final_place, "End", 0)
        _add_transition(net, "end_t", "End", process_end_places, [final_place])

    return net


def write_pnml(net: PetriNet, output_path: pathlib.Path) -> None:
    pnml = ET.Element("pnml", {"xmlns": "http://www.pnml.org/version-2009/grammar/pnml"})
    net_elem = ET.SubElement(
        pnml,
        "net",
        {"id": "bpmn_local", "type": "http://www.pnml.org/version-2009/grammar/ptnet"},
    )

    for place in net.places.values():
        place_elem = ET.SubElement(net_elem, "place", {"id": place.pid})
        name = ET.SubElement(place_elem, "name")
        ET.SubElement(name, "text").text = place.name
        marking = ET.SubElement(place_elem, "initialMarking")
        ET.SubElement(marking, "text").text = str(place.tokens)

    for transition in net.transitions.values():
        transition_elem = ET.SubElement(net_elem, "transition", {"id": transition.tid})
        name = ET.SubElement(transition_elem, "name")
        ET.SubElement(name, "text").text = transition.name

    for arc in net.arcs:
        ET.SubElement(
            net_elem,
            "arc",
            {"id": arc.aid, "source": arc.source, "target": arc.target},
        )

    ET.indent(pnml, space="  ")
    output_path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        + ET.tostring(pnml, encoding="unicode"),
        encoding="utf-8",
    )


def convert_file(input_path: pathlib.Path, output_path: pathlib.Path) -> None:
    model = parse_bpmn(input_path)
    net = convert_bpmn_to_pn(model)
    write_pnml(net, output_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert BPMN to PNML locally")
    parser.add_argument("input", type=pathlib.Path, help="Path to BPMN file")
    parser.add_argument(
        "-o",
        "--output",
        type=pathlib.Path,
        help="Output PNML file (default: input name with .pnml)",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    output = args.output or args.input.with_suffix(".pnml")
    convert_file(args.input, output)


if __name__ == "__main__":
    main()
