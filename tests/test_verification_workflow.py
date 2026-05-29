import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from scripts.verification_utils import parse_bool_result
from scripts.verify_workflow import collect_formula_paths, run_verification


MINIMAL_PNML = """<?xml version="1.0" encoding="UTF-8"?>
<pnml>
  <net id="n1">
    <place id="p_start">
      <name><text>Start</text></name>
      <initialMarking><text>1</text></initialMarking>
    </place>
    <place id="p_end">
      <name><text>End</text></name>
      <initialMarking><text>0</text></initialMarking>
    </place>
    <transition id="t_fire">
      <name><text>Fire</text></name>
    </transition>
    <arc id="a1" source="p_start" target="t_fire" />
    <arc id="a2" source="t_fire" target="p_end" />
  </net>
</pnml>
"""


class TestVerificationWorkflow(unittest.TestCase):
    def test_parse_bool_result(self):
        self.assertTrue(parse_bool_result("true\n"))
        self.assertFalse(parse_bool_result("pbessolve result: false\n"))

    def test_collect_formula_paths_merges_explicit_and_directory_inputs(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = pathlib.Path(tmp_dir)
            one = tmp / "a.mcf"
            two = tmp / "b.mcf"
            one.write_text("true", encoding="utf-8")
            two.write_text("false", encoding="utf-8")

            collected = collect_formula_paths([one], [tmp])

        self.assertEqual(collected, sorted({one.resolve(), two.resolve()}))

    def test_run_verification_on_pnml_with_mocked_tools(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = pathlib.Path(tmp_dir)
            pnml_path = tmp / "toy.pnml"
            formula_path = tmp / "reachable.mcf"
            output_dir = tmp / "artifacts"
            pnml_path.write_text(MINIMAL_PNML, encoding="utf-8")
            formula_path.write_text("[true*]<true>true\n", encoding="utf-8")

            def fake_resolve_tool(name: str) -> str:
                return name

            def fake_run(cmd: list[str], timeout: int = 120, check: bool = True) -> subprocess.CompletedProcess[str]:
                tool = pathlib.Path(cmd[0]).name
                if tool == "mcrl22lps":
                    pathlib.Path(cmd[2]).write_text("lps", encoding="utf-8")
                    return subprocess.CompletedProcess(cmd, 0, "", "")
                if tool == "lps2lts":
                    pathlib.Path(cmd[-1]).write_text("lts", encoding="utf-8")
                    return subprocess.CompletedProcess(cmd, 0, "", "")
                if tool == "ltsconvert":
                    target = pathlib.Path(cmd[-1])
                    if target.suffix == ".aut":
                        target.write_text('des (0,1,2)\n(0,"fire",1)\n', encoding="utf-8")
                    else:
                        target.write_text("digraph { 0 -> 1 }", encoding="utf-8")
                    return subprocess.CompletedProcess(cmd, 0, "", "")
                if tool == "ltsinfo":
                    return subprocess.CompletedProcess(
                        cmd,
                        0,
                        "Number of states: 2\nNumber of transitions: 1\nLTS is deterministic: yes\n",
                        "",
                    )
                if tool in {"lps2pbes", "lts2pbes"}:
                    pathlib.Path(cmd[-1]).write_text("pbes", encoding="utf-8")
                    return subprocess.CompletedProcess(cmd, 0, "", "")
                if tool == "pbes2bool":
                    return subprocess.CompletedProcess(cmd, 0, "true\n", "")
                raise AssertionError(f"Unexpected command: {cmd}")

            with mock.patch("scripts.verify_workflow.resolve_tool", side_effect=fake_resolve_tool):
                with mock.patch("scripts.verify_workflow.run", side_effect=fake_run):
                    summary = run_verification(
                        pnml_path,
                        output_dir,
                        formula_paths=[formula_path],
                        max_place_tokens=1,
                        max_lts_states=25,
                        timeout=5,
                    )

            self.assertEqual(summary["max_place_tokens"], 1)
            self.assertEqual(summary["max_lts_states"], 25)
            self.assertEqual(summary["lts_info"]["Number of states"], "2")
            self.assertEqual(len(summary["properties"]), 1)
            self.assertTrue(summary["properties"][0]["result"])
            self.assertTrue((output_dir / "toy_bounded.mcrl2").exists())
            self.assertTrue((output_dir / "toy_bounded_lts.svg").exists())
            self.assertTrue((output_dir / "README.md").exists())
            self.assertTrue((output_dir / "results.json").exists())


if __name__ == "__main__":
    unittest.main()
