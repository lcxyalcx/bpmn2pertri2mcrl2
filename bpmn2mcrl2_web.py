#!/usr/bin/env python3
"""Convert BPMN to mCRL2 using bpmn2petrinet.com for BPMN→PNML."""

from __future__ import annotations

import argparse
import pathlib
import tempfile
from dataclasses import dataclass

from playwright.sync_api import sync_playwright

from pnml2mcrl2 import convert_file


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

    bpmn_content = bpmn_path.read_text(encoding="utf-8")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=config.headless)
        page = browser.new_page()
        page.goto("https://bpmn2petrinet.com/", wait_until="domcontentloaded")

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
        browser.close()


def convert_bpmn_to_mcrl2(
    bpmn_path: pathlib.Path,
    output_mcrl2: pathlib.Path,
    config: WebConfig | None = None,
) -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        pnml_path = pathlib.Path(tmp_dir) / (bpmn_path.stem + ".pnml")
        bpmn_to_pnml_via_web(bpmn_path, pnml_path, config=config)
        convert_file(pnml_path, output_mcrl2)


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
    convert_bpmn_to_mcrl2(args.input, output, config=config)


if __name__ == "__main__":
    main()
