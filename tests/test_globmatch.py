"""Glob matching over browse paths — no server, no network."""

import pytest

from opcua_tagmap.globmatch import filter_tags, translate
from opcua_tagmap.model import TagNode

import re


def tag(path):
    name = path.rsplit("/", 1)[-1]
    return TagNode(browse_path=path, display_name=name, namespace=2,
                   identifier_type="s", identifier=name, datatype="Double")


def m(pattern, path):
    return re.match(translate(pattern), path) is not None


# --- segment awareness: * must not cross a slash -----------------------------

@pytest.mark.parametrize("pattern, path, expected", [
    ("Objects/Panel/C*", "Objects/Panel/CoilVoltage_V", True),
    ("Objects/Panel/C*", "Objects/Panel/Temperature_C", False),
    # the important one: a single * stops at the slash
    ("Objects/*", "Objects/Panel/CoilVoltage_V", False),
    ("Objects/*", "Objects/Panel", True),
    ("Objects/*/CoilVoltage_V", "Objects/Panel/CoilVoltage_V", True),
    ("Objects/*/*", "Objects/Panel/CoilVoltage_V", True),
])
def test_star_is_segment_bounded(pattern, path, expected):
    assert m(pattern, path) is expected


# --- ** crosses segments -----------------------------------------------------

@pytest.mark.parametrize("path, expected", [
    ("Objects/Temperature", True),            # zero segments between
    ("Objects/Panel/Temperature", True),
    ("Objects/A/B/C/Temperature", True),
    ("Objects/Panel/Temperature_C", False),   # still anchored at the end
])
def test_double_star_spans_segments(path, expected):
    assert m("Objects/**/Temperature", path) is expected


def test_question_mark_and_class():
    assert m("Objects/Panel/MV0?", "Objects/Panel/MV01")
    assert not m("Objects/Panel/MV0?", "Objects/Panel/MV012")
    assert m("Objects/Panel/MV[01]1", "Objects/Panel/MV01")
    assert not m("Objects/Panel/MV[23]1", "Objects/Panel/MV01")


def test_negated_class():
    assert m("Objects/Panel/MV[!9]1", "Objects/Panel/MV01")
    assert not m("Objects/Panel/MV[!0]1", "Objects/Panel/MV01")


def test_dots_are_literal_not_regex_wildcards():
    """A regex-naive implementation would match 'AxB' here."""
    assert m("Objects/A.B", "Objects/A.B")
    assert not m("Objects/A.B", "Objects/AxB")


# --- filter_tags -------------------------------------------------------------

PANEL = [tag(f"Objects/ProtectionPanel/{n}") for n in
         ["CoilVoltage_V", "CurrentDraw_A", "CycleTime_ms", "Temperature_C",
          "Pressure_mbar", "ContactorState", "FaultFlag"]]


def test_no_patterns_keeps_everything():
    assert len(filter_tags(PANEL)) == 7


def test_include_narrows():
    kept = filter_tags(PANEL, include=["Objects/ProtectionPanel/C*"])
    assert {t.display_name for t in kept} == {
        "CoilVoltage_V", "CurrentDraw_A", "CycleTime_ms", "ContactorState"}


def test_exclude_applies_after_include():
    kept = filter_tags(PANEL,
                       include=["Objects/ProtectionPanel/C*"],
                       exclude=["**/ContactorState"])
    assert {t.display_name for t in kept} == {
        "CoilVoltage_V", "CurrentDraw_A", "CycleTime_ms"}


def test_multiple_includes_are_a_union():
    kept = filter_tags(PANEL, include=["**/FaultFlag", "**/Pressure_mbar"])
    assert len(kept) == 2


def test_no_match_yields_empty_not_everything():
    """The failure mode that would make the tool silently collect nothing."""
    assert filter_tags(PANEL, include=["Objects/NoSuchThing/*"]) == []
