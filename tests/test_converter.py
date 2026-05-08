import pathlib
import tempfile
import unittest

from pnml2mcrl2 import convert_file


class TestConverter(unittest.TestCase):
    def test_pizza_pnml(self):
        base_dir = pathlib.Path(__file__).resolve().parents[1]
        input_path = base_dir / "examples" / "pizza.pnml"
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = pathlib.Path(tmp_dir) / "pizza.mcrl2"
            convert_file(input_path, output_path)
            content = output_path.read_text(encoding="utf-8")

        self.assertIn("init P(init);", content)
        self.assertIn("fire_t_0", content)
        self.assertIn("fire_t_1", content)
        self.assertIn("p_0", content)
        self.assertIn("p_1", content)
        self.assertIn("p_2", content)


if __name__ == "__main__":
    unittest.main()
