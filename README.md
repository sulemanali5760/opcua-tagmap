# opcua-tagmap

[![CI](https://github.com/sulemanali5760/opcua-tagmap/actions/workflows/ci.yml/badge.svg)](https://github.com/sulemanali5760/opcua-tagmap/actions/workflows/ci.yml)

Browse an OPC UA server, filter the tags you want with glob patterns, and get
collector configuration you can paste straight into Telegraf.

It does not collect, store or display anything — Telegraf, InfluxDB, Grafana,
ThingsBoard and Node-RED already do that well. This fills the gap *before* them:
turning a PLC's address space into their config without typing it by hand.

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
calls browse-based discovery *"one of the most requested features for
large-scale OPC-UA deployments"*. ThingsBoard users hit the same wall
([#9594](https://github.com/thingsboard/thingsboard/issues/9594)). Commercial
products sell a "tag browser" as a headline feature. The open stack has none.

## Install

```bash
pip install opcua-tagmap
```

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

Export the inventory for a commissioning document:

```bash
opcua-tagmap browse opc.tcp://192.168.0.10:4840 --format csv --out tags.csv
```

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
| `--format text\|csv\|json` | `browse` output shape |
| `--out FILE` | write to a file instead of stdout |

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

**Not yet verified against a real PLC.** The simulator is
[`asyncua`](https://github.com/FreeOpcUa/opcua-asyncio)-based and well behaved;
real servers have deeper trees, permission boundaries and vendor quirks in
NodeId encoding. If you run it against real hardware, an issue describing what
happened is genuinely useful.

## Licence

MIT — see [LICENSE](LICENSE).
