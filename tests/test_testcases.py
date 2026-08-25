"""Stub generation is a pure function, so it needs no server to test."""

import yaml

from opcua_tagmap.emit import testcases
from opcua_tagmap.model import TagNode

TAGS = [
    TagNode("Objects/Panel/CoilVoltage_V", "CoilVoltage_V", 2, "s",
            "CoilVoltage_V", "Double"),
    TagNode("Objects/Panel/ContactorState", "ContactorState", 2, "s",
            "ContactorState", "String"),
    TagNode("Objects/Panel/FaultFlag", "FaultFlag", 2, "s",
            "FaultFlag", "Boolean"),
    TagNode("Objects/Panel/Count", "Count", 3, "i", "1042", "Int32"),
]

ENDPOINT = "opc.tcp://plc:4840"


def _parse(tag):
    return yaml.safe_load(testcases.render(tag, ENDPOINT))


# --- what gets a stub at all ------------------------------------------------

def test_only_numeric_tags_get_a_stub():
    stubs, skipped = testcases.plan(TAGS, ENDPOINT)
    assert len(stubs) == 2                      # Double + Int32
    assert {t.display_name for t, _ in skipped} == {"ContactorState", "FaultFlag"}


def test_skipped_tags_carry_a_reason():
    _, skipped = testcases.plan(TAGS, ENDPOINT)
    for _, reason in skipped:
        assert reason.strip()


def test_integers_count_as_numeric():
    assert testcases.is_numeric(TAGS[3])
    assert not testcases.is_numeric(TAGS[1])


# --- the stub is valid, and wired to the right tag --------------------------

def test_stub_is_valid_yaml_and_names_the_variable():
    doc = _parse(TAGS[0])
    assert doc["variable"] == "CoilVoltage_V"
    assert doc["node_id"].startswith("ns=2;s=CoilVoltage_V")
    assert doc["test_id"] == "TC-CoilVoltage_V"


def test_filename_is_derived_from_the_tag():
    assert testcases.stub_filename(TAGS[0]) == "TC-CoilVoltage_V.yaml"


def test_filename_is_sanitised():
    odd = TagNode("Objects/A/B", "Flow rate/min", 2, "s", "x", "Double")
    name = testcases.stub_filename(odd)
    assert "/" not in name and " " not in name


# --- the part that matters: no invented limits ------------------------------

def test_stub_never_invents_a_limit():
    """A generated spec must not judge anything until a human fills it in."""
    for tag in TAGS:
        if not testcases.is_numeric(tag):
            continue
        spec = _parse(tag).get("spec") or {}
        assert spec.get("min") is None, "generator must not guess a lower limit"
        assert spec.get("max") is None, "generator must not guess an upper limit"


def test_stub_says_it_is_unfinished():
    text = testcases.render(TAGS[0], ENDPOINT)
    assert "STUB" in text
    assert "TODO" in text


def test_condition_window_is_commented_out_by_default():
    doc = _parse(TAGS[0])
    assert "condition_variable" not in doc


# --- unit guessing ----------------------------------------------------------

def test_units_are_read_from_the_tag_suffix():
    assert testcases.guess_units("CoilVoltage_V") == ("V", True)
    assert testcases.guess_units("CurrentDraw_A") == ("A", True)
    assert testcases.guess_units("Temperature_C") == ("C", True)
    assert testcases.guess_units("Pressure_mbar") == ("mbar", True)


def test_longer_unit_suffixes_win_over_shorter_ones():
    # "_mbar" must not be read as "_bar", nor "_mV" as "_V"
    assert testcases.guess_units("Tank_mbar") == ("mbar", True)
    assert testcases.guess_units("Signal_mV") == ("mV", True)


def test_unknown_units_are_flagged_rather_than_guessed():
    units, guessed = testcases.guess_units("SomeOpaqueName")
    assert guessed is False
    assert units == "TODO"
    assert "could not infer" in testcases.render(
        TagNode("Objects/A/SomeOpaqueName", "SomeOpaqueName", 2, "s",
                "x", "Double"), ENDPOINT)
