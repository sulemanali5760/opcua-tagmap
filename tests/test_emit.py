"""Emitters are pure functions, so they need no server to test."""

import csv
import io
import json
import tomllib

from opcua_tagmap.emit import table, telegraf
from opcua_tagmap.model import TagNode

TAGS = [
    TagNode("Objects/Panel/CoilVoltage_V", "CoilVoltage_V", 2, "s",
            "CoilVoltage_V", "Double"),
    TagNode("Objects/Panel/ContactorState", "ContactorState", 2, "s",
            "ContactorState", "String"),
    TagNode("Objects/Panel/Count", "Count", 3, "i", "1042", "Int32"),
]


# --- telegraf ---------------------------------------------------------------

def test_telegraf_output_is_valid_toml():
    parsed = tomllib.loads(telegraf.render(TAGS, "opc.tcp://plc:4840"))
    assert parsed["inputs"]["opcua"][0]["endpoint"] == "opc.tcp://plc:4840"


def test_telegraf_carries_every_node_with_its_nodeid():
    parsed = tomllib.loads(telegraf.render(TAGS, "opc.tcp://plc:4840"))
    nodes = parsed["inputs"]["opcua"][0]["nodes"]
    assert len(nodes) == 3
    by_name = {n["name"]: n for n in nodes}
    assert by_name["CoilVoltage_V"]["namespace"] == "2"
    assert by_name["CoilVoltage_V"]["identifier_type"] == "s"
    # a numeric NodeId must survive as i, not be coerced to a string type
    assert by_name["Count"]["identifier_type"] == "i"
    assert by_name["Count"]["identifier"] == "1042"
    assert by_name["Count"]["namespace"] == "3"


def test_telegraf_escapes_quotes_so_output_still_parses():
    nasty = [TagNode('Objects/P/we"ird', 'we"ird', 2, "s", 'we"ird', "Double")]
    parsed = tomllib.loads(telegraf.render(nasty, 'opc.tcp://plc:4840'))
    assert parsed["inputs"]["opcua"][0]["nodes"][0]["name"] == 'we"ird'


# --- table ------------------------------------------------------------------

def test_csv_round_trips_every_row():
    rows = list(csv.DictReader(io.StringIO(table.to_csv(TAGS))))
    assert len(rows) == 3
    assert rows[0]["browse_path"] == "Objects/Panel/CoilVoltage_V"
    assert rows[0]["node_id"] == "ns=2;s=CoilVoltage_V"


def test_json_includes_the_canonical_node_id():
    data = json.loads(table.to_json(TAGS))
    assert data[2]["node_id"] == "ns=3;i=1042"


def test_text_renders_one_line_per_tag():
    assert len(table.to_text(TAGS).strip().splitlines()) == 3


def test_text_of_nothing_is_empty_not_a_crash():
    assert table.to_text([]) == ""
