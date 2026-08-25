"""Command line entry point.

    opcua-tagmap browse opc.tcp://plc:4840
    opcua-tagmap gen telegraf opc.tcp://plc:4840 --include 'Objects/Plant1/*/MV*'
"""

import argparse
import sys
from pathlib import Path

from .browse import DEFAULT_MAX_DEPTH, DEFAULT_MAX_NODES, browse_sync
from .emit import table, telegraf, testcases
from .globmatch import filter_tags


def _add_common(parser: argparse.ArgumentParser, with_out: bool = True) -> None:
    parser.add_argument("endpoint", help="opc.tcp://host:port/path")
    parser.add_argument("--root", default=None,
                        help='start below this NodeId, e.g. "ns=2;s=Plant1"')
    parser.add_argument("--include", action="append", default=[], metavar="GLOB",
                        help="keep browse paths matching this pattern (repeatable)")
    parser.add_argument("--exclude", action="append", default=[], metavar="GLOB",
                        help="drop browse paths matching this pattern (repeatable)")
    parser.add_argument("--max-depth", type=int, default=DEFAULT_MAX_DEPTH)
    parser.add_argument("--max-nodes", type=int, default=DEFAULT_MAX_NODES)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--include-standard", action="store_true",
                        help="also include the OPC UA standard namespace "
                             "(ns=0) — the server's own diagnostic tree, "
                             "roughly 250 nodes, excluded by default")
    if with_out:
        parser.add_argument("--out", default=None,
                            help="write here instead of stdout")


def _collect(args):
    """Browse, filter, and fail loudly if nothing survived."""
    result = browse_sync(args.endpoint, root=args.root,
                         max_depth=args.max_depth, max_nodes=args.max_nodes,
                         timeout=args.timeout,
                         skip_standard=not args.include_standard)

    for err in result.errors:
        print(f"warning: could not browse {err}", file=sys.stderr)
    if result.truncated:
        print(f"warning: stopped at --max-nodes {args.max_nodes}; "
              "output is incomplete", file=sys.stderr)

    tags = filter_tags(result.tags, args.include, args.exclude)

    if not tags:
        # Emitting an empty config would look like success and silently
        # collect nothing. Say so and exit non-zero.
        if result.tags and (args.include or args.exclude):
            print(f"error: no nodes matched. {len(result.tags)} variable(s) "
                  "found on the server but every one was filtered out.",
                  file=sys.stderr)
        else:
            print("error: no variables found on the server.", file=sys.stderr)
        sys.exit(1)

    return tags


def _write(text: str, out: str | None) -> None:
    if out:
        Path(out).write_text(text, encoding="utf-8")
        print(f"wrote {out}", file=sys.stderr)
    else:
        sys.stdout.write(text)


def _write_testcases(tags, args) -> int:
    """Write one stub per numeric tag, never clobbering filled-in work."""
    stubs, skipped = testcases.plan(tags, args.endpoint)

    for tag, reason in skipped:
        print(f"skipped {tag.display_name}: {reason}", file=sys.stderr)

    if not stubs:
        print("error: no numeric variables among the matched tags, so there "
              "is nothing a min/max spec could check.", file=sys.stderr)
        return 1

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    written = kept = 0
    for filename, text in stubs:
        path = out_dir / filename
        if path.exists() and not args.overwrite:
            kept += 1
            continue
        path.write_text(text, encoding="utf-8")
        written += 1

    print(f"wrote {written} stub(s) to {out_dir}/", file=sys.stderr)
    if kept:
        print(f"left {kept} existing file(s) alone — pass --overwrite to "
              "replace them", file=sys.stderr)
    if written:
        print("every stub needs a limit before it means anything: "
              "uncomment min/max and fill in the real number.", file=sys.stderr)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="opcua-tagmap", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_browse = sub.add_parser("browse", help="list the variables on a server")
    p_browse.add_argument("--format", choices=["text", "csv", "json"],
                          default="text")
    _add_common(p_browse)

    p_gen = sub.add_parser("gen", help="generate collector configuration")
    gen_sub = p_gen.add_subparsers(dest="target", required=True)
    p_telegraf = gen_sub.add_parser("telegraf", help="Telegraf [[inputs.opcua]]")
    p_telegraf.add_argument("--input-name", default="opcua",
                            help="value for the Telegraf input `name` field")
    _add_common(p_telegraf)

    p_tc = gen_sub.add_parser(
        "testcases",
        help="test-case stubs, one YAML file per numeric tag")
    p_tc.add_argument("--out-dir", default="test_cases", metavar="DIR",
                      help="directory to write stubs into (default: test_cases)")
    p_tc.add_argument("--overwrite", action="store_true",
                      help="replace stubs that already exist — this discards "
                           "limits you have filled in, so it is off by default")
    _add_common(p_tc, with_out=False)

    args = parser.parse_args(argv)
    tags = _collect(args)

    if args.command == "browse":
        renderer = {"text": table.to_text, "csv": table.to_csv,
                    "json": table.to_json}[args.format]
        _write(renderer(tags), args.out)
    elif args.target == "testcases":
        return _write_testcases(tags, args)
    else:
        _write(telegraf.render(tags, args.endpoint, args.input_name), args.out)

    print(f"{len(tags)} node(s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
