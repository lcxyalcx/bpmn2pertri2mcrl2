import pathlib
import tempfile
import unittest
import xml.etree.ElementTree as ET

from bpmn2pnml_local import convert_file as convert_bpmn_to_pnml
from pnml2mcrl2 import convert_file


class TestConverter(unittest.TestCase):
    def test_pizza_pnml(self):
        base_dir = pathlib.Path(__file__).resolve().parents[1]
        input_path = base_dir / "examples" / "pizza.pnml"
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = pathlib.Path(tmp_dir) / "pizza.mcrl2"
            convert_file(input_path, output_path)
            content = output_path.read_text(encoding="utf-8")

        self.assertIn("init P(m_init);", content)
        self.assertIn("makepizza", content)
        self.assertIn("shippizza", content)
        self.assertIn("p_0", content)
        self.assertIn("p_1", content)
        self.assertIn("p_2", content)

    def test_official_pizza_pnml(self):
        base_dir = pathlib.Path(__file__).resolve().parents[1]
        input_path = base_dir / "examples" / "pizza_official.pnml"
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = pathlib.Path(tmp_dir) / "pizza_official.mcrl2"
            convert_file(input_path, output_path)
            content = output_path.read_text(encoding="utf-8")

        self.assertIn("init P(m_init);", content)
        self.assertIn("a_end", content)
        self.assertIn("p_23", content)
        self.assertIn("m_init(p_23) = 1;", content)
        self.assertIn("% Source Petri net: 24 places, 18 transitions, 46 arcs", content)
        self.assertIn("t_0/order_a_pizza = Order a pizza", content)
        self.assertIn("t_8/bake_the_pizza = Bake the pizza", content)
        self.assertIn("t_10/receive_payment = Receive payment", content)

    def test_official_pizza_local_bpmn_to_pnml(self):
        base_dir = pathlib.Path(__file__).resolve().parents[1]
        input_path = base_dir / "examples" / "pizza_official.bpmn"
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = pathlib.Path(tmp_dir) / "pizza_official_local.pnml"
            convert_bpmn_to_pnml(input_path, output_path)
            root = ET.parse(output_path).getroot()

        counts = {"place": 0, "transition": 0, "arc": 0}
        transition_names = set()
        for element in root.iter():
            tag = element.tag.split("}", 1)[-1]
            if tag in counts:
                counts[tag] += 1
            if tag == "transition":
                text = element.find(".//{*}name/{*}text")
                if text is not None and text.text:
                    transition_names.add(text.text)

        self.assertEqual(counts, {"place": 27, "transition": 23, "arc": 56})
        self.assertIn("Receive payment", transition_names)
        self.assertIn("choose _6-424", transition_names)

    def test_generic_action_names_are_available(self):
        base_dir = pathlib.Path(__file__).resolve().parents[1]
        input_path = base_dir / "examples" / "pizza.pnml"
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = pathlib.Path(tmp_dir) / "pizza.mcrl2"
            convert_file(input_path, output_path, semantic_actions=False)
            content = output_path.read_text(encoding="utf-8")

        self.assertIn("fire_t_0", content)
        self.assertIn("fire_t_1", content)

    def test_bounded_model_adds_post_place_guards(self):
        base_dir = pathlib.Path(__file__).resolve().parents[1]
        input_path = base_dir / "examples" / "pizza_official.pnml"
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = pathlib.Path(tmp_dir) / "pizza_official_bounded.mcrl2"
            convert_file(input_path, output_path, max_place_tokens=1)
            content = output_path.read_text(encoding="utf-8")

        self.assertIn("% Max place tokens: 1", content)
        self.assertIn("(m(p_2) < 1) -> a_60_minutes", content)


if __name__ == "__main__":
    unittest.main()
