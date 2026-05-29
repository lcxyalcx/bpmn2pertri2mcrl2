import pathlib
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

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

    def test_large_pnml_generation_uses_sparse_iterative_updates(self):
        from pnml2mcrl2 import Arc, Net, Place, Transition, generate_mcrl2

        place_count = 1200
        places = {
            f"p{i:04d}": Place(
                pid=f"p{i:04d}",
                name=f"Place {i}",
                tokens=1 if i == 0 else 0,
            )
            for i in range(place_count)
        }
        transitions = {"t0": Transition(tid="t0", name="Step")}
        arcs = [
            Arc(source="p0000", target="t0"),
            Arc(source="t0", target="p0001"),
        ]
        net = Net(places=places, transitions=transitions, arcs=arcs)

        content = generate_mcrl2(net)
        update_line = next(
            line.strip()
            for line in content.splitlines()
            if line.strip().startswith("update_t_0(m) =")
        )

        self.assertEqual(update_line.count("if(p =="), 2)
        self.assertIn("m(p_0) - 1", update_line)
        self.assertIn("m(p_1) + 1", update_line)

    def test_compatibility_checker_accepts_supported_bpmn(self):
        import sys

        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
        from check_bpmn_compatibility import analyze_bpmn

        base_dir = pathlib.Path(__file__).resolve().parents[1]
        report = analyze_bpmn(base_dir / "examples" / "pizza.bpmn", timeout=30)
        self.assertTrue(report.compatible)
        self.assertTrue(report.mcrl2_generated)

    def test_exclusive_gateway_bpmn_to_pnml(self):
        bpmn = """<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL">
  <bpmn:process id="Process_1">
    <bpmn:startEvent id="Start_1" />
    <bpmn:exclusiveGateway id="Gateway_1" />
    <bpmn:task id="Task_A" name="A" />
    <bpmn:task id="Task_B" name="B" />
    <bpmn:endEvent id="End_1" />
    <bpmn:sequenceFlow id="Flow_1" sourceRef="Start_1" targetRef="Gateway_1" />
    <bpmn:sequenceFlow id="Flow_2" sourceRef="Gateway_1" targetRef="Task_A" />
    <bpmn:sequenceFlow id="Flow_3" sourceRef="Gateway_1" targetRef="Task_B" />
    <bpmn:sequenceFlow id="Flow_4" sourceRef="Task_A" targetRef="End_1" />
    <bpmn:sequenceFlow id="Flow_5" sourceRef="Task_B" targetRef="End_1" />
  </bpmn:process>
</bpmn:definitions>
"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            bpmn_path = pathlib.Path(tmp_dir) / "xor_split.bpmn"
            pnml_path = pathlib.Path(tmp_dir) / "xor_split.pnml"
            bpmn_path.write_text(bpmn, encoding="utf-8")
            convert_bpmn_to_pnml(bpmn_path, pnml_path)
            root = ET.parse(pnml_path).getroot()

        transition_names = {
            element.find(".//{*}name/{*}text").text
            for element in root.iter()
            if element.tag.split("}", 1)[-1] == "transition"
            for _ in [0]
            if element.find(".//{*}name/{*}text") is not None
            and element.find(".//{*}name/{*}text").text
        }
        self.assertIn("choose Flow_2", transition_names)
        self.assertIn("choose Flow_3", transition_names)

    def test_inclusive_gateway_split_generates_subset_transitions(self):
        from bpmn2pnml_local import convert_bpmn_to_pn, parse_bpmn

        bpmn = """<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL">
  <bpmn:process id="Process_1">
    <bpmn:startEvent id="Start_1" />
    <bpmn:inclusiveGateway id="Gateway_1" />
    <bpmn:task id="Task_A" name="A" />
    <bpmn:task id="Task_B" name="B" />
    <bpmn:endEvent id="End_1" />
    <bpmn:sequenceFlow id="Flow_1" sourceRef="Start_1" targetRef="Gateway_1" />
    <bpmn:sequenceFlow id="Flow_2" sourceRef="Gateway_1" targetRef="Task_A" />
    <bpmn:sequenceFlow id="Flow_3" sourceRef="Gateway_1" targetRef="Task_B" />
    <bpmn:sequenceFlow id="Flow_4" sourceRef="Task_A" targetRef="End_1" />
    <bpmn:sequenceFlow id="Flow_5" sourceRef="Task_B" targetRef="End_1" />
  </bpmn:process>
</bpmn:definitions>
"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            bpmn_path = pathlib.Path(tmp_dir) / "or_split.bpmn"
            bpmn_path.write_text(bpmn, encoding="utf-8")
            net = convert_bpmn_to_pn(parse_bpmn(bpmn_path))

        self.assertEqual(len(net.transitions), 7)
        self.assertTrue(any(name.startswith("activate ") for name in (t.name for t in net.transitions.values())))

    def test_intermediate_throw_event_produces_message_place(self):
        from bpmn2pnml_local import convert_bpmn_to_pn, parse_bpmn

        bpmn = """<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL">
  <bpmn:process id="Process_1">
    <bpmn:startEvent id="Start_1" />
    <bpmn:task id="Task_1" name="Prepare" />
    <bpmn:intermediateThrowEvent id="Throw_1" name="Notify" />
    <bpmn:endEvent id="End_1" />
    <bpmn:sequenceFlow id="Flow_1" sourceRef="Start_1" targetRef="Task_1" />
    <bpmn:sequenceFlow id="Flow_2" sourceRef="Task_1" targetRef="Throw_1" />
    <bpmn:sequenceFlow id="Flow_3" sourceRef="Throw_1" targetRef="End_1" />
  </bpmn:process>
  <bpmn:process id="Process_2">
    <bpmn:startEvent id="Start_2" />
    <bpmn:endEvent id="End_2" />
    <bpmn:sequenceFlow id="Flow_4" sourceRef="Start_2" targetRef="End_2" />
  </bpmn:process>
  <bpmn:messageFlow id="Msg_1" sourceRef="Throw_1" targetRef="Start_2" />
</bpmn:definitions>
"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            bpmn_path = pathlib.Path(tmp_dir) / "throw.bpmn"
            bpmn_path.write_text(bpmn, encoding="utf-8")
            net = convert_bpmn_to_pn(parse_bpmn(bpmn_path))

        self.assertIn("Msg_1", net.places)
        throw_transitions = [t for t in net.transitions.values() if t.name == "Notify"]
        self.assertEqual(len(throw_transitions), 1)
        throw_tid = throw_transitions[0].tid
        post_places = {arc.target for arc in net.arcs if arc.source == throw_tid}
        self.assertIn("Flow_3", post_places)
        self.assertIn("Msg_1", post_places)

    def test_compatibility_checker_accepts_exclusive_gateway(self):
        import sys

        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
        from check_bpmn_compatibility import analyze_bpmn

        bpmn = """<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL">
  <bpmn:process id="Process_1">
    <bpmn:startEvent id="Start_1" />
    <bpmn:exclusiveGateway id="Gateway_1" />
    <bpmn:task id="Task_1" name="A" />
    <bpmn:endEvent id="End_1" />
    <bpmn:sequenceFlow id="Flow_1" sourceRef="Start_1" targetRef="Gateway_1" />
    <bpmn:sequenceFlow id="Flow_2" sourceRef="Gateway_1" targetRef="Task_1" />
    <bpmn:sequenceFlow id="Flow_3" sourceRef="Task_1" targetRef="End_1" />
  </bpmn:process>
</bpmn:definitions>
"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            bpmn_path = pathlib.Path(tmp_dir) / "xor.bpmn"
            bpmn_path.write_text(bpmn, encoding="utf-8")
            report = analyze_bpmn(bpmn_path, timeout=30)

        self.assertTrue(report.compatible)
        self.assertTrue(report.mcrl2_generated)

    def test_user_task_is_converted_as_task(self):
        from bpmn2pnml_local import convert_bpmn_to_pn, parse_bpmn

        bpmn = """<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL">
  <bpmn:process id="Process_1">
    <bpmn:startEvent id="Start_1" />
    <bpmn:userTask id="Task_1" name="Review" />
    <bpmn:endEvent id="End_1" />
    <bpmn:sequenceFlow id="Flow_1" sourceRef="Start_1" targetRef="Task_1" />
    <bpmn:sequenceFlow id="Flow_2" sourceRef="Task_1" targetRef="End_1" />
  </bpmn:process>
</bpmn:definitions>
"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            bpmn_path = pathlib.Path(tmp_dir) / "user_task.bpmn"
            bpmn_path.write_text(bpmn, encoding="utf-8")
            model = parse_bpmn(bpmn_path)
            net = convert_bpmn_to_pn(model)

        self.assertEqual(model.nodes["Task_1"].tag, "task")
        self.assertEqual(model.nodes["Task_1"].original_tag, "userTask")
        self.assertIn("Task_1", net.transitions)

    def test_subprocess_is_flattened(self):
        from bpmn2pnml_local import convert_bpmn_to_pn, parse_bpmn

        bpmn = """<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL">
  <bpmn:process id="Process_1">
    <bpmn:startEvent id="Start_1" />
    <bpmn:subProcess id="Sub_1">
      <bpmn:startEvent id="SubStart" />
      <bpmn:task id="Inner" name="Inside" />
      <bpmn:endEvent id="SubEnd" />
      <bpmn:sequenceFlow id="Flow_in_1" sourceRef="SubStart" targetRef="Inner" />
      <bpmn:sequenceFlow id="Flow_in_2" sourceRef="Inner" targetRef="SubEnd" />
    </bpmn:subProcess>
    <bpmn:endEvent id="End_1" />
    <bpmn:sequenceFlow id="Flow_1" sourceRef="Start_1" targetRef="Sub_1" />
    <bpmn:sequenceFlow id="Flow_2" sourceRef="Sub_1" targetRef="End_1" />
  </bpmn:process>
</bpmn:definitions>
"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            bpmn_path = pathlib.Path(tmp_dir) / "subprocess.bpmn"
            bpmn_path.write_text(bpmn, encoding="utf-8")
            model = parse_bpmn(bpmn_path)
            net = convert_bpmn_to_pn(model)

        self.assertIn("Inner", model.nodes)
        self.assertNotIn("Sub_1", model.nodes)
        self.assertTrue(any(t.name == "Inside" for t in net.transitions.values()))
        self.assertIn("Flow_1_entry", model.sequence_flows)

    def test_boundary_event_uses_attached_activity_input(self):
        from bpmn2pnml_local import convert_bpmn_to_pn, parse_bpmn

        bpmn = """<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL">
  <bpmn:process id="Process_1">
    <bpmn:startEvent id="Start_1" />
    <bpmn:task id="Task_1" name="Work" />
    <bpmn:boundaryEvent id="Boundary_1" name="Timeout" attachedToRef="Task_1" />
    <bpmn:task id="Task_2" name="Escalate" />
    <bpmn:endEvent id="End_1" />
    <bpmn:sequenceFlow id="Flow_1" sourceRef="Start_1" targetRef="Task_1" />
    <bpmn:sequenceFlow id="Flow_2" sourceRef="Task_1" targetRef="End_1" />
    <bpmn:sequenceFlow id="Flow_3" sourceRef="Boundary_1" targetRef="Task_2" />
    <bpmn:sequenceFlow id="Flow_4" sourceRef="Task_2" targetRef="End_1" />
  </bpmn:process>
</bpmn:definitions>
"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            bpmn_path = pathlib.Path(tmp_dir) / "boundary.bpmn"
            bpmn_path.write_text(bpmn, encoding="utf-8")
            net = convert_bpmn_to_pn(parse_bpmn(bpmn_path))

        boundary = net.transitions["Boundary_1"]
        pre = {arc.source for arc in net.arcs if arc.target == "Boundary_1"}
        self.assertIn("Flow_1", pre)
        self.assertEqual(boundary.name, "Timeout")


if __name__ == "__main__":
    unittest.main()
