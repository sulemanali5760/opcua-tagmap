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


# --- names must be unique: Telegraf rejects a config with two nodes of the same name ----------

def test_repeated_names_get_their_parent_in_front():
    tags = [TagNode("Objects/Plant/TIC101/PV", "PV", 2, "s", "TIC101.PV", "Double"),
            TagNode("Objects/Plant/TI102/PV", "PV", 2, "s", "TI102.PV", "Double"),
            TagNode("Objects/Plant/TIC101/SP", "SP", 2, "s", "TIC101.SP", "Double")]
    assert telegraf.field_names(tags) == ["TIC101_PV", "TI102_PV", "SP"]
    nodes = tomllib.loads(telegraf.render(tags, "opc.tcp://plc:4840"))["inputs"]["opcua"][0]["nodes"]
    assert len({n["name"] for n in nodes}) == 3


def test_names_stay_unique_when_the_parent_repeats_too():
    tags = [TagNode("Objects/Line1/Pump/Speed", "Speed", 2, "s", "a", "Double"),
            TagNode("Objects/Line2/Pump/Speed", "Speed", 2, "s", "b", "Double")]
    assert telegraf.field_names(tags) == ["Line1_Pump_Speed", "Line2_Pump_Speed"]


def test_unique_names_are_left_alone():
    assert telegraf.field_names(TAGS) == ["CoilVoltage_V", "ContactorState", "Count"]
