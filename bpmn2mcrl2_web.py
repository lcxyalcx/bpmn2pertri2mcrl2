#!/usr/bin/env python3
"""Convert BPMN to mCRL2 using bpmn2petrinet.com for BPMN→PNML."""

from __future__ import annotations

import argparse
import pathlib
import re
import tempfile
from dataclasses import dataclass

from playwright.sync_api import sync_playwright

from pnml2mcrl2 import convert_file


def _read_xml_text(path: pathlib.Path) -> str:
    raw = path.read_bytes()
    head = raw[:200].decode("ascii", errors="ignore")
    match = re.search(r'encoding=["\']([^"\']+)["\']', head, flags=re.IGNORECASE)
    encoding = match.group(1) if match else "utf-8"
    return raw.decode(encoding)


@dataclass
class WebConfig:
    apply_decorators: str = "no"
    apply_collapse: str = "no"
    apply_timed_tasks: str = "no"
    node_size: int = 40
    flow_scaling: float = 1.5
    graphviz_text: str = "outside"
    headless: bool = True
    timeout_ms: int = 30000


def bpmn_to_pnml_via_web(
    bpmn_path: pathlib.Path,
    output_pnml: pathlib.Path,
    config: WebConfig | None = None,
) -> None:
    if config is None:
        config = WebConfig()

    bpmn_content = _read_xml_text(bpmn_path)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=config.headless)
        try:
            page = browser.new_page()
            page.set_default_timeout(config.timeout_ms)
            page.goto(
                "https://bpmn2petrinet.com/",
                wait_until="domcontentloaded",
                timeout=config.timeout_ms,
            )

            pnml_content = page.evaluate(
                """
                async ({ bpmn, config }) => {
                    const { Importer, Parser, Converter, Exporter, Config } = await import('/src/bpmn2petri/index.js');
                    Config.withDecorators = config.apply_decorators === 'yes';
                    Config.withCollapsedXor = config.apply_collapse === 'yes';
                    Config.timedTasks = config.apply_timed_tasks === 'yes';
                    Config.nodeSize = config.node_size;
                    Config.scale = config.flow_scaling;
                    Config.graphvizTextOutside = config.graphviz_text === 'outside';

                    const importer = new Importer();
                    await importer.importString(bpmn);
                    const parser = new Parser(importer.XML);
                    const converter = new Converter(parser.BPMN);
                    const petrinet = converter.convert();
                    const exporter = new Exporter(petrinet);
                    exporter.export();
                    return exporter.getResult();
                }
                """,
                {
                    "bpmn": bpmn_content,
                    "config": {
                        "apply_decorators": config.apply_decorators,
                        "apply_collapse": config.apply_collapse,
                        "apply_timed_tasks": config.apply_timed_tasks,
                        "node_size": config.node_size,
                        "flow_scaling": config.flow_scaling,
                        "graphviz_text": config.graphviz_text,
                    },
                },
            )
            output_pnml.write_text(pnml_content, encoding="utf-8")
        finally:
            browser.close()


def convert_bpmn_to_mcrl2(
    bpmn_path: pathlib.Path,
    output_mcrl2: pathlib.Path,
    config: WebConfig | None = None,
    pnml_output: pathlib.Path | None = None,
    semantic_actions: bool = True,
    max_place_tokens: int | None = None,
) -> None:
    if pnml_output is not None:
        bpmn_to_pnml_via_web(bpmn_path, pnml_output, config=config)
        convert_file(
            pnml_output,
            output_mcrl2,
            semantic_actions=semantic_actions,
            max_place_tokens=max_place_tokens,
        )
        return

    with tempfile.TemporaryDirectory() as tmp_dir:
        pnml_path = pathlib.Path(tmp_dir) / (bpmn_path.stem + ".pnml")
        bpmn_to_pnml_via_web(bpmn_path, pnml_path, config=config)
        convert_file(
            pnml_path,
            output_mcrl2,
            semantic_actions=semantic_actions,
            max_place_tokens=max_place_tokens,
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert BPMN to mCRL2 via bpmn2petrinet.com"
    )
    parser.add_argument("input", type=pathlib.Path, help="Path to BPMN file")
    parser.add_argument(
        "-o",
        "--output",
        type=pathlib.Path,
        help="Output mCRL2 file (default: input name with .mcrl2)",
    )
    parser.add_argument(
        "--pnml-output",
        type=pathlib.Path,
        help="Optional PNML output path for the intermediate Petri net",
    )
    parser.add_argument(
        "--generic-actions",
        action="store_true",
        help="Use fire_t_i action names instead of semantic transition names",
    )
    parser.add_argument(
        "--max-place-tokens",
        type=int,
        help="Bound generated transitions so no place can exceed this token count",
    )
    parser.add_argument("--decorators", choices=["yes", "no"], default="no")
    parser.add_argument("--collapse-xor", choices=["yes", "no"], default="no")
    parser.add_argument("--timed-tasks", choices=["yes", "no"], default="no")
    parser.add_argument("--node-size", type=int, default=40)
    parser.add_argument("--flow-scaling", type=float, default=1.5)
    parser.add_argument("--graphviz-text", choices=["outside", "inside"], default="outside")
    parser.add_argument("--headed", action="store_true", help="Run with visible browser")
    parser.add_argument("--timeout", type=int, default=30000, help="Download timeout (ms)")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    output = args.output or args.input.with_suffix(".mcrl2")
    config = WebConfig(
        apply_decorators=args.decorators,
        apply_collapse=args.collapse_xor,
        apply_timed_tasks=args.timed_tasks,
        node_size=args.node_size,
        flow_scaling=args.flow_scaling,
        graphviz_text=args.graphviz_text,
        headless=not args.headed,
        timeout_ms=args.timeout,
    )
    convert_bpmn_to_mcrl2(
        args.input,
        output,
        config=config,
        pnml_output=args.pnml_output,
        semantic_actions=not args.generic_actions,
        max_place_tokens=args.max_place_tokens,
    )


if __name__ == "__main__":
    main()
