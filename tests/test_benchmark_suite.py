import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_benchmark_suite import run_suite  # noqa: E402


class TestBenchmarkSuite(unittest.TestCase):
    def test_benchmark_suite_manifest_cases_are_compatible(self):
        manifest = ROOT / "examples" / "benchmarks" / "suite_manifest.json"
        with tempfile.TemporaryDirectory() as tmp_dir:
            payload = run_suite(manifest, pathlib.Path(tmp_dir), timeout=30)

        summary = payload["summary"]
        self.assertEqual(summary["total"], 11)
        self.assertEqual(summary["incompatible"], 0)
        self.assertEqual(summary["compatible"], 11)
        self.assertIn("gateway", summary["category_summary"])
        self.assertIn("message-flow", summary["category_summary"])
        self.assertIn("subprocess", summary["category_summary"])
        self.assertIn("event-based", summary["category_summary"])
        self.assertIn("cross-pool", summary["category_summary"])
        self.assertIn("multi-instance", summary["category_summary"])
        self.assertIn("multi-collaboration", summary["category_summary"])


if __name__ == "__main__":
    unittest.main()
