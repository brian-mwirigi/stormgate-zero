"""SAM wire grammar and SCADA radio fault parser."""

from backend.agents.sam_radar_tracker import (
    build_object_prompt,
    decode_rle,
    extract_dbz_boxes_frame0,
    parse_sam_wire,
)
from backend.agents.voice_scada_bridge import parse_faults


def test_object_prompt_grammar_and_round_trip():
    boxes = [(0.12, 0.18, 0.31, 0.40), (0.55, 0.62, 0.80, 0.88)]
    prompt = build_object_prompt(boxes)
    assert prompt.startswith("<0f><objects>")
    assert "<concept>" not in prompt
    wire = (
        '<0f><frame index="1" t="5">'
        '<obj id="0"><box x1="0.1200" y1="0.1800" x2="0.3100" y2="0.4000"/>'
        '<mask codec="rle" width="4" height="1">2 2</mask></obj>'
        "</frame></0f>"
    )
    frames = parse_sam_wire(wire)
    assert frames[0]["index"] == 1
    assert frames[0]["objects"][0]["box"] == (0.12, 0.18, 0.31, 0.40)
    mask = frames[0]["objects"][0]["mask"]
    assert mask is not None
    assert mask.reshape(-1).tolist() == [0, 0, 1, 1]
    # A leading zero run is how the grammar encodes a mask that starts hot.
    assert decode_rle([0, 4], 4, 1).reshape(-1).tolist() == [1, 1, 1, 1]


def test_frame0_seeder_finds_a_core():
    boxes = extract_dbz_boxes_frame0(None)
    assert boxes, "Frame 0 should expose at least one >45 dBZ core"
    x1, y1, x2, y2 = boxes[0]
    assert 0.0 <= x1 < x2 <= 1.2
    assert 0.0 <= y1 < y2 <= 1.2


def test_jammed_gate_radio_call():
    text = "Operator 4: Sluice Gate 2 is mechanically jammed at 50 percent open."
    faults = parse_faults(text)
    assert len(faults) == 1
    fault = faults[0]
    assert fault["type"] == "valve_jam"
    assert fault["orifice_id"] == "OR2"
    assert fault["locked_setting"] == 0.5
    assert fault["role"] == "SCADA Operator"


def test_concept_and_boxes_are_not_combined():
    prompt = build_object_prompt([(0.1, 0.1, 0.2, 0.2)])
    assert "red storm cell" not in prompt
