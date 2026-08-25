"""Walk an OPC UA server's address space and collect its variables.

All protocol work is asyncua's. This module only decides where to descend,
when to stop, and what to record.
"""

import asyncio
from typing import Iterable

from asyncua import Client, ua

from .model import TagNode

DEFAULT_MAX_DEPTH = 12
DEFAULT_MAX_NODES = 10_000

# NodeId encodings, as the rest of the world writes them in config files.
_ID_TYPE = {
    ua.NodeIdType.Numeric: "i",
    ua.NodeIdType.String: "s",
    ua.NodeIdType.Guid: "g",
    ua.NodeIdType.ByteString: "b",
    ua.NodeIdType.TwoByte: "i",
    ua.NodeIdType.FourByte: "i",
}


class BrowseResult:
    def __init__(self, tags: list[TagNode], errors: list[str], truncated: bool):
        self.tags = tags
        self.errors = errors
        self.truncated = truncated


async def _read_datatype(node) -> str:
    try:
        variant = await node.read_data_type_as_variant_type()
        return variant.name
    except Exception:
        return "Unknown"


async def _walk(node, path: str, depth: int, state: dict) -> None:
    if depth > state["max_depth"] or len(state["tags"]) >= state["max_nodes"]:
        if len(state["tags"]) >= state["max_nodes"]:
            state["truncated"] = True
        return

    try:
        children = await node.get_children()
    except Exception as e:
        # A permission error part-way down a real server must not abort the
        # whole browse — record it and carry on with the rest of the tree.
        state["errors"].append(f"{path}: {e}")
        return

    for child in children:
        # Namespace 0 is reserved for the OPC UA standard: the Server object
        # alone carries ~250 diagnostic nodes (MaxSessions, ServerCapabilities,
        # RedundancySupport...). Machine tags always live in ns>=1, so without
        # this the real tags are buried. --include-standard opts back in.
        if state["skip_standard"] and child.nodeid.NamespaceIndex == 0:
            continue

        try:
            name = (await child.read_browse_name()).Name
            node_class = await child.read_node_class()
        except Exception as e:
            state["errors"].append(f"{path}: {e}")
            continue

        child_path = f"{path}/{name}"

        if node_class == ua.NodeClass.Variable:
            if len(state["tags"]) >= state["max_nodes"]:
                state["truncated"] = True
                return
            nid = child.nodeid
            state["tags"].append(TagNode(
                browse_path=child_path,
                display_name=name,
                namespace=nid.NamespaceIndex,
                identifier_type=_ID_TYPE.get(nid.NodeIdType, "s"),
                identifier=str(nid.Identifier),
                datatype=await _read_datatype(child),
            ))
        elif node_class == ua.NodeClass.Object:
            await _walk(child, child_path, depth + 1, state)


async def browse(endpoint: str,
                 root: str | None = None,
                 max_depth: int = DEFAULT_MAX_DEPTH,
                 max_nodes: int = DEFAULT_MAX_NODES,
                 timeout: float = 10.0,
                 skip_standard: bool = True) -> BrowseResult:
    """Collect every Variable under `root` (default: the Objects folder).

    `root` may be a NodeId string such as "ns=2;s=ProtectionPanel" to start
    part-way down a large server.

    `skip_standard` drops the OPC UA standard namespace (ns=0), which is what
    makes the output about the machine rather than about the server.
    """
    state = {"tags": [], "errors": [], "truncated": False,
             "max_depth": max_depth, "max_nodes": max_nodes,
             "skip_standard": skip_standard}

    client = Client(url=endpoint, timeout=timeout)
    async with client:
        if root:
            start = client.get_node(root)
            start_path = (await start.read_browse_name()).Name
        else:
            start = client.nodes.objects
            start_path = "Objects"
        await _walk(start, start_path, 0, state)

    state["tags"].sort(key=lambda t: t.browse_path)
    return BrowseResult(state["tags"], state["errors"], state["truncated"])


def browse_sync(*args, **kwargs) -> BrowseResult:
    return asyncio.run(browse(*args, **kwargs))
