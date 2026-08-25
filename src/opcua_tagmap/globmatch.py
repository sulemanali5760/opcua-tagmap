"""Glob matching over browse paths.

This is the piece Telegraf users keep asking for (influxdata/telegraf#18529):
say `Objects/Plant1/*/MV*` instead of listing four hundred nodes by hand.

Segment-aware, so `*` stops at a `/`:

    *           any run of characters within one segment
    ?           one character within one segment
    [abc]       character class; [!abc] negates
    **          any number of whole segments, including none

Pure functions — no OPC UA, no I/O, no network.
"""

import re
from typing import Iterable

from .model import TagNode


def translate(pattern: str) -> str:
    """Glob pattern -> anchored regex source."""
    out: list[str] = []
    i, n = 0, len(pattern)

    while i < n:
        c = pattern[i]

        if c == "*":
            if pattern[i:i + 2] == "**":
                i += 2
                # `**/` and a trailing `**` both mean "zero or more segments"
                if pattern[i:i + 1] == "/":
                    i += 1
                    out.append("(?:[^/]*/)*")
                else:
                    out.append(".*")
            else:
                out.append("[^/]*")
                i += 1

        elif c == "?":
            out.append("[^/]")
            i += 1

        elif c == "[":
            j = i + 1
            if j < n and pattern[j] in "!^":
                j += 1
            if j < n and pattern[j] == "]":  # a ] right after [ is a literal
                j += 1
            while j < n and pattern[j] != "]":
                j += 1
            if j >= n:  # unclosed bracket: treat as a literal [
                out.append(re.escape(c))
                i += 1
            else:
                inner = pattern[i + 1:j]
                if inner[:1] in ("!", "^"):
                    inner = "^" + inner[1:]
                out.append("[" + inner.replace("\\", "\\\\") + "]")
                i = j + 1

        else:
            out.append(re.escape(c))
            i += 1

    return "^" + "".join(out) + "$"


def compile_patterns(patterns: Iterable[str]) -> list[re.Pattern]:
    return [re.compile(translate(p)) for p in patterns]


def matches_any(path: str, compiled: list[re.Pattern]) -> bool:
    return any(rx.match(path) for rx in compiled)


def filter_tags(tags: Iterable[TagNode],
                include: Iterable[str] | None = None,
                exclude: Iterable[str] | None = None) -> list[TagNode]:
    """Keep tags matching any include pattern, then drop any matching exclude.

    No include patterns means keep everything — the common case of wanting the
    whole server.
    """
    inc = compile_patterns(include or [])
    exc = compile_patterns(exclude or [])

    kept = []
    for tag in tags:
        if inc and not matches_any(tag.browse_path, inc):
            continue
        if exc and matches_any(tag.browse_path, exc):
            continue
        kept.append(tag)
    return kept
