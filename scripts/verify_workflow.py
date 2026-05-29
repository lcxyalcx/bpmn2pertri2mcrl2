#!/usr/bin/env python3
"""Run a generic BPMN/PNML/mCRL2 verification and LTS visualization workflow."""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
from dataclasses import dataclass


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bpmn2pnml_local import convert_file as convert_bpmn_to_pnml  # noqa: E402
from pnml2mcrl2 import convert_file as convert_pnml_to_mcrl2  # noqa: E402
from scripts.verification_utils import (  # noqa: E402
    parse_bool_result,
    parse_ltsinfo,
    resolve_tool,
    write_lts_svg,
)


@dataclass(frozen=True)
class FormulaResult:
    formula: pathlib.Path
    pbes: pathlib.Path
    result: bool
    backend: str
    solver_output: str


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

def relative_path(path: pathlib.Path) -> str:
    if path.is_relative_to(ROOT):
        return path.relative_to(ROOT).as_posix()
    return str(path).replace("\\", "/")


def collect_formula_paths(
    formulas: list[pathlib.Path],
    formula_dirs: list[pathlib.Path],
) -> list[pathlib.Path]:
    collected: dict[pathlib.Path, None] = {}
    for path in formulas:
        if not path.is_file():
            raise FileNotFoundError(path)
        collected[path.resolve()] = None
    for directory in formula_dirs:
        if not directory.is_dir():
            raise FileNotFoundError(directory)
        for path in sorted(directory.glob("*.mcf")):
            collected[path.resolve()] = None
    return sorted(collected.keys())


def prepare_model(
    input_path: pathlib.Path,
    output_dir: pathlib.Path,
    max_place_tokens: int | None,
) -> dict[str, pathlib.Path]:
    input_path = input_path.resolve()
    suffix = input_path.suffix.lower()
    model_stem = input_path.stem

    if suffix == ".bpmn":
        pnml_path = output_dir / f"{model_stem}.pnml"
        convert_bpmn_to_pnml(input_path, pnml_path)
        mcrl2_name = f"{model_stem}_bounded.mcrl2" if max_place_tokens is not None else f"{model_stem}.mcrl2"
        mcrl2_path = output_dir / mcrl2_name
        convert_pnml_to_mcrl2(
            pnml_path,
            mcrl2_path,
            max_place_tokens=max_place_tokens,
        )
        return {"input": input_path, "pnml": pnml_path, "mcrl2": mcrl2_path}

    if suffix == ".pnml":
        mcrl2_name = f"{model_stem}_bounded.mcrl2" if max_place_tokens is not None else f"{model_stem}.mcrl2"
        mcrl2_path = output_dir / mcrl2_name
        convert_pnml_to_mcrl2(
            input_path,
            mcrl2_path,
            max_place_tokens=max_place_tokens,
        )
        return {"input": input_path, "pnml": input_path, "mcrl2": mcrl2_path}

    if suffix == ".mcrl2":
        if max_place_tokens is not None:
            raise ValueError("--max-place-tokens is only supported for BPMN/PNML input")
        return {"input": input_path, "mcrl2": input_path}

    raise ValueError(f"Unsupported input type: {input_path.suffix}")


def solve_formulas(
    lps_path: pathlib.Path,
    lts_path: pathlib.Path,
    output_dir: pathlib.Path,
    formula_paths: list[pathlib.Path],
    timeout: int,
    backend: str = "auto",
) -> list[FormulaResult]:
    results: list[FormulaResult] = []
    if not formula_paths:
        return results

    lps2pbes = resolve_tool("lps2pbes")
    lts2pbes = resolve_tool("lts2pbes")
    pbes2bool = resolve_tool("pbes2bool")

    for formula in formula_paths:
        backends = [backend] if backend in {"lps", "lts"} else ["lps", "lts"]
        errors: list[str] = []
        for current_backend in backends:
            pbes_path = output_dir / f"{formula.stem}_{current_backend}.pbes"
            try:
                if current_backend == "lps":
                    run(
                        [
                            lps2pbes,
                            "--structured",
                            "--preprocess-modal-operators",
                            f"--formula={formula}",
                            str(lps_path),
                            str(pbes_path),
                        ],
                        timeout=timeout,
                    )
                else:
                    run(
                        [
                            lts2pbes,
                            "--preprocess-modal-operators",
                            f"--formula={formula}",
                            f"--lps={lps_path}",
                            str(lts_path),
                            str(pbes_path),
                        ],
                        timeout=timeout,
                    )
                solved = run([pbes2bool, str(pbes_path)], timeout=timeout)
                solver_output = solved.stdout + solved.stderr
                results.append(
                    FormulaResult(
                        formula=formula,
                        pbes=pbes_path,
                        result=parse_bool_result(solver_output),
                        backend=current_backend,
                        solver_output=solver_output.strip(),
                    )
                )
                break
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{current_backend}: {exc}")
        else:
            raise RuntimeError(
                f"Failed to solve formula {formula} using backends {backends}: {'; '.join(errors)}"
            )
    return results


def write_summary_svg(results: list[FormulaResult], svg_path: pathlib.Path, title: str) -> None:
    width = 980
    row_height = 70
    height = 110 + row_height * max(1, len(results))
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="32" y="42" font-family="Helvetica" font-size="24" font-weight="700">{title}</text>',
        '<text x="32" y="70" font-family="Helvetica" font-size="14" fill="#475569">Each row is the direct PBES solver result for one modal formula.</text>',
    ]
    y = 98
    if not results:
        lines.append('<text x="32" y="122" font-family="Helvetica" font-size="14" fill="#475569">No formulas were provided for this run.</text>')
    for item in results:
        fill = "#dcfce7" if item.result else "#fee2e2"
        stroke = "#16a34a" if item.result else "#dc2626"
        lines.extend(
            [
                f'<rect x="32" y="{y}" width="916" height="50" rx="8" fill="{fill}" stroke="{stroke}"/>',
                f'<text x="52" y="{y + 22}" font-family="Helvetica" font-size="15" font-weight="700">{item.formula.name}</text>',
                f'<text x="52" y="{y + 40}" font-family="Helvetica" font-size="13" fill="#334155">result={str(item.result).lower()} · backend={item.backend} · pbes={item.pbes.name}</text>',
            ]
        )
        y += row_height
    lines.append("</svg>")
    svg_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_report(summary: dict[str, object], output_dir: pathlib.Path) -> None:
    lines = [
        "# Verification Results",
        "",
        f"- Input: `{summary['input']}`",
        f"- Generated mCRL2: `{summary['generated']['mcrl2']}`",
        f"- LPS: `{summary['generated']['lps']}`",
        f"- LTS: `{summary['generated']['lts']}`",
        f"- LTS SVG: `{summary['generated']['lts_svg']}`",
        f"- Max LTS states: {summary['max_lts_states']}",
    ]
    if summary["max_place_tokens"] is not None:
        lines.append(f"- Max place tokens: {summary['max_place_tokens']}")
    if summary["generated"].get("pnml"):
        lines.append(f"- PNML: `{summary['generated']['pnml']}`")

    lines.extend(["", "## LTS", ""])
    for key, value in summary["lts_info"].items():
        lines.append(f"- {key}: {value}")

    lines.extend(["", "## Modal Formulas", ""])
    if summary["properties"]:
        lines.append("| Formula | Result | Backend | PBES |")
        lines.append("| --- | --- | --- | --- |")
        for item in summary["properties"]:
            lines.append(
                f"| `{pathlib.Path(item['formula']).name}` | {str(item['result']).lower()} | `{item['backend']}` | `{item['pbes']}` |"
            )
    else:
        lines.append("No `.mcf` files were provided.")

    (output_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_verification(
    input_path: pathlib.Path,
    output_dir: pathlib.Path,
    formula_paths: list[pathlib.Path],
    max_place_tokens: int | None = None,
    max_lts_states: int = 200,
    timeout: int = 120,
    formula_backend: str = "auto",
) -> dict[str, object]:
    mcrl22lps = resolve_tool("mcrl22lps")
    lps2lts = resolve_tool("lps2lts")
    ltsconvert = resolve_tool("ltsconvert")
    ltsinfo = resolve_tool("ltsinfo")

    output_dir.mkdir(parents=True, exist_ok=True)
    model = prepare_model(input_path, output_dir, max_place_tokens)

    mcrl2_path = model["mcrl2"]
    base_name = mcrl2_path.stem
    lps_path = output_dir / f"{base_name}.lps"
    lts_path = output_dir / f"{base_name}.lts"
    aut_path = output_dir / f"{base_name}.aut"
    dot_path = output_dir / f"{base_name}.dot"
    lts_svg_path = output_dir / f"{base_name}_lts.svg"

    run([mcrl22lps, str(mcrl2_path), str(lps_path)], timeout=timeout)
    run([lps2lts, f"--max={max_lts_states}", str(lps_path), str(lts_path)], timeout=timeout)
    run([ltsconvert, "--out=aut", str(lts_path), str(aut_path)], timeout=timeout)
    run([ltsconvert, "--out=dot", str(lts_path), str(dot_path)], timeout=timeout)
    lts_info_result = run([ltsinfo, str(lts_path)], timeout=timeout)
    lts_info = parse_ltsinfo(lts_info_result.stdout + lts_info_result.stderr)
    write_lts_svg(aut_path, lts_svg_path, max_states=max_lts_states)

    formula_results = solve_formulas(
        lps_path,
        lts_path,
        output_dir,
        formula_paths,
        timeout=timeout,
        backend=formula_backend,
    )
    summary_svg_path = output_dir / f"{base_name}_verification_summary.svg"
    write_summary_svg(formula_results, summary_svg_path, f"Verification Summary: {base_name}")

    summary = {
        "input": relative_path(model["input"]),
        "max_place_tokens": max_place_tokens,
        "max_lts_states": max_lts_states,
        "generated": {
            "pnml": relative_path(model["pnml"]) if "pnml" in model else None,
            "mcrl2": relative_path(mcrl2_path),
            "lps": relative_path(lps_path),
            "lts": relative_path(lts_path),
            "lts_aut": relative_path(aut_path),
            "lts_dot": relative_path(dot_path),
            "lts_svg": relative_path(lts_svg_path),
            "summary_svg": relative_path(summary_svg_path),
        },
        "lts_info": lts_info,
        "properties": [
            {
                "formula": relative_path(item.formula),
                "pbes": relative_path(item.pbes),
                "result": item.result,
                "backend": item.backend,
                "solver_output": item.solver_output,
            }
            for item in formula_results
        ],
    }
    (output_dir / "results.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    write_report(summary, output_dir)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run BPMN/PNML/mCRL2 verification and LTS visualization"
    )
    parser.add_argument("input", type=pathlib.Path, help="Input BPMN, PNML, or mCRL2 file")
    parser.add_argument(
        "-o",
        "--output-dir",
        type=pathlib.Path,
        help="Directory for generated verification artifacts (default: docs/verification/<input-stem>)",
    )
    parser.add_argument(
        "--formula",
        action="append",
        type=pathlib.Path,
        default=[],
        help="Formula file (.mcf). Can be repeated.",
    )
    parser.add_argument(
        "--formula-dir",
        action="append",
        type=pathlib.Path,
        default=[],
        help="Directory containing .mcf files. Can be repeated.",
    )
    parser.add_argument(
        "--max-place-tokens",
        type=int,
        help="Bound the generated model so each place can hold at most this many tokens",
    )
    parser.add_argument("--max-lts-states", type=int, default=200)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument(
        "--formula-backend",
        choices=["auto", "lps", "lts"],
        default="auto",
        help="Backend for modal formula solving",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    output_dir = args.output_dir or (ROOT / "docs" / "verification" / args.input.stem)
    formula_paths = collect_formula_paths(args.formula, args.formula_dir)
    summary = run_verification(
        args.input,
        output_dir,
        formula_paths=formula_paths,
        max_place_tokens=args.max_place_tokens,
        max_lts_states=args.max_lts_states,
        timeout=args.timeout,
        formula_backend=args.formula_backend,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
