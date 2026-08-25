"""The one data structure everything else passes around."""

from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class TagNode:
    """A single readable variable found on an OPC UA server.

    `browse_path` is the human-readable route to the node, slash separated and
    starting at Objects — e.g. "Objects/ProtectionPanel/CoilVoltage_V". It is
    what glob patterns match against, and what a person recognises.

    The NodeId trio (`namespace`, `identifier_type`, `identifier`) is what
    every downstream collector actually needs in its config.
    """

    browse_path: str
    display_name: str
    namespace: int
    identifier_type: str  # "s" string, "i" numeric, "g" guid, "b" bytestring
    identifier: str
    datatype: str  # variant type name: Double, String, Boolean, ...

    @property
    def node_id(self) -> str:
        """Canonical OPC UA NodeId string, e.g. ns=2;s=CoilVoltage_V."""
        return f"ns={self.namespace};{self.identifier_type}={self.identifier}"

    def as_dict(self) -> dict:
        d = asdict(self)
        d["node_id"] = self.node_id
        return d


FIELDS = ["browse_path", "display_name", "namespace", "identifier_type",
          "identifier", "datatype", "node_id"]
