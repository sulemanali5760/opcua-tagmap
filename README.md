# opcua-tagmap

[![CI](https://github.com/sulemanali5760/opcua-tagmap/actions/workflows/ci.yml/badge.svg)](https://github.com/sulemanali5760/opcua-tagmap/actions/workflows/ci.yml)

Browse an OPC UA server, filter the tags you want with glob patterns, and get
a tag inventory (CSV/JSON), a static Telegraf config, or test-case stubs.

It does not collect, store or display anything — Telegraf, InfluxDB, Grafana,
ThingsBoard and Node-RED already do that well. This works *before* them:
turning a PLC's address space into files you can read, review and version.

## The problem

Pointing any IIoT collector at a real machine means enumerating every node:

```toml
[[inputs.opcua.nodes]]
  name = "host_MV01"
  namespace = "2"
  identifier_type = "s"
  identifier = "Plant.Device1.MV01"

# ... repeated for MV02 ... MV99, by hand
```

Telegraf's own issue [#18529](https://github.com/influxdata/telegraf/issues/18529)
called browse-based discovery *"one of the most requested features for
large-scale OPC-UA deployments"*. ThingsBoard users hit the same wall
([#9594](https://github.com/thingsboard/thingsboard/issues/9594)).

### Telegraf has this built in now

That issue was closed in May 2026: Telegraf merged browse-based discovery with
glob patterns (`[inputs.opcua.browse]`, pull request
[#18831](https://github.com/influxdata/telegraf/pull/18831)); releases from
1.39.0 (June 2026) on were published after that merge. **If you run a current
Telegraf and want it to discover nodes by itself at start-up, use that, not this tool.**

What `opcua-tagmap` is still for:

- **A static config you can review.** The generated file lists every node, so a
  change on the PLC shows up as a diff in version control instead of silently
  changing what is collected.
- **Older Telegraf versions** that do not have the browse section.
- **A tag inventory** as CSV or JSON for commissioning documents, independent of any collector.
- **Test-case stubs** for acceptance tests (below).

## Install

With internet:

```bash
pip install https://github.com/sulemanali5760/opcua-tagmap/releases/download/v0.2.0/opcua_tagmap-0.2.0-py3-none-any.whl
```

Without internet (a plant PC, a commissioning laptop on the machine network): download the offline bundle
for your system from the [latest release](https://github.com/sulemanali5760/opcua-tagmap/releases/latest), carry
it over on a USB stick, unzip it and run inside the folder:

```bash
python -m pip install --no-index --find-links . opcua-tagmap
```

The bundle holds this tool and every package it needs; nothing is downloaded. Each bundle is installed in a
clean environment and started once before it is published. Python 3.11 or newer. Not on PyPI yet.

## Use

See what is on a server:

```bash
opcua-tagmap browse opc.tcp://192.168.0.10:4840
```

```
Objects/ProtectionPanel/CoilVoltage_V    ns=2;s=CoilVoltage_V     Double
Objects/ProtectionPanel/ContactorState   ns=2;s=ContactorState    String
Objects/ProtectionPanel/CurrentDraw_A    ns=2;s=CurrentDraw_A     Double
...
```

Generate a Telegraf input for a subset:

```bash
opcua-tagmap gen telegraf opc.tcp://192.168.0.10:4840 \
  --include 'Objects/Plant1/*/MV*' \
  --out telegraf.conf
```

Scaffold acceptance tests for a whole panel:

```bash
opcua-tagmap gen testcases opc.tcp://192.168.0.10:4840 \
  --include 'Objects/ProtectionPanel/*' \
  --out-dir test_cases/
```

```
skipped ContactorState: String - a min/max spec cannot express it
skipped FaultFlag: Boolean - a min/max spec cannot express it
wrote 5 stub(s) to test_cases/
every stub needs a limit before it means anything: uncomment min/max and fill in the real number.
```

One YAML file per numeric tag, in the format
[opc-ua-test-automation-pipeline](https://github.com/sulemanali5760/opc-ua-test-automation-pipeline)
reads. On a machine with a hundred tags, this turns *write a hundred files*
into *delete the eighty-five you do not care about and fill in fifteen numbers*.

**It never guesses a limit.** A generated stub has `min` and `max` commented
out, so it cannot pass or fail until someone opens a datasheet and types the
real number. An invented limit produces a test that passes for no reason,
which is worse than having no test.

Re-running is safe: files that already exist are left alone, so adding a tag
next month gives you only the new stubs. `--overwrite` forces the issue.

Export the inventory for a commissioning document:

```bash
opcua-tagmap browse opc.tcp://192.168.0.10:4840 --format csv --out tags.csv
```

## Names in the Telegraf output

Telegraf rejects a config in which two nodes share a name, and plants reuse
names all the time (every control loop has a `PV`). A name that occurs more
than once gets its parent in front: `PV` becomes `TIC101_PV` and `TI102_PV`;
names that are already unique are left alone.

## Structured variables

Members of a structured variable are listed too (`Recipe/Setpoint`,
`Recipe/Duration`): this is how controllers expose a STRUCT. Properties that
only describe a variable, such as `EURange` or `EngineeringUnits`, are not tags
and are left out.

## Glob patterns

Matched against the browse path, and segment-aware — `*` stops at a `/`:

| Pattern | Matches |
|---|---|
| `Objects/Plant1/*/MV*` | any `MV…` one level under any child of `Plant1` |
| `Objects/**/Temperature` | `Temperature` at any depth |
| `Objects/Panel/MV0?` | `MV01`, `MV02`, … but not `MV012` |
| `Objects/Panel/MV[01]1` | `MV01` and `MV11` |

`--include` is a union — repeat it. `--exclude` is applied afterwards.
No `--include` means every variable on the server.

## Options

| Flag | Purpose |
|---|---|
| `--root ns=2;s=Plant1` | start part-way down instead of at Objects |
| `--max-depth`, `--max-nodes` | stop a huge server from running away |
| `--include-standard` | also return the OPC UA standard namespace (see below) |
| `--format text\|csv\|json` | `browse` output shape |
| `--out FILE` | write to a file instead of stdout |

**Namespace 0 is excluded by default.** Every OPC UA server exposes a standard
`Server` object — roughly 250 diagnostic nodes like `MaxSessions`,
`ServerCapabilities` and `RedundancySupport`. Browsing a small demo server
raw returns 255 nodes, of which 7 are the machine. Since the standard
namespace is always ns=0 and machine tags always live in ns≥1, ns=0 is dropped
unless you ask for it with `--include-standard`.

If a pattern matches nothing, the tool **exits non-zero and writes no file**,
rather than handing you a valid-looking config that collects nothing.

Nodes that cannot be browsed — permissions, for instance — are reported as
warnings on stderr and the rest of the tree is still walked.

## Roadmap

- `gen thingsboard` — IoT Gateway `opcua.json`
- `gen nodered` — flow JSON
- `gen ditto` — Eclipse Ditto Thing JSON
- diff two browses: which tags appeared or vanished between machine revisions

## What is tested

CI runs the unit tests, then the whole tool against a simulated OPC UA server
with a known address space, asserting that a browse finds exactly its seven
variables, that the generated TOML parses and carries all seven NodeIds, that
`Objects/ProtectionPanel/C*` selects exactly four, and that a pattern matching
nothing fails instead of writing an empty config.

A second test server, started inside `pytest`, covers what the panel simulator
does not have: two objects with a variable of the same name, and a structured
variable with member variables and a property.

**No security yet.** The tool connects anonymously without encryption, and the
generated Telegraf block says so (`security_policy = "None"`). A server that
only accepts encrypted or logged-in sessions cannot be browsed with it; to find
out what such a server wants, see
[opcua-doctor](https://github.com/sulemanali5760/opcua-doctor).

**Not yet verified against a real PLC.** The simulator is
[`asyncua`](https://github.com/FreeOpcUa/opcua-asyncio)-based and well behaved;
real servers have deeper trees, permission boundaries and vendor quirks in
NodeId encoding. If you run it against real hardware, an issue describing what
happened is genuinely useful.

## Licence

MIT — see [LICENSE](LICENSE).
