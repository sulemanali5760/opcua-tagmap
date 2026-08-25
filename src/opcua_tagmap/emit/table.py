"""Plain tag inventory: CSV or JSON.

Useful on its own — a commissioning engineer wants the list of what is on the
server regardless of which platform, if any, will collect it.
"""

import csv
import io
import json

from ..model import FIELDS, TagNode


def to_csv(tags: list[TagNode]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    for tag in tags:
        writer.writerow(tag.as_dict())
    return buf.getvalue()


def to_json(tags: list[TagNode]) -> str:
    return json.dumps([t.as_dict() for t in tags], indent=2) + "\n"


def to_text(tags: list[TagNode]) -> str:
    """Aligned columns for reading in a terminal."""
    if not tags:
        return ""
    width = max(len(t.browse_path) for t in tags)
    return "".join(
        f"{t.browse_path:<{width}}  {t.node_id:<28}  {t.datatype}\n"
        for t in tags
    )
