from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List


class WorkflowNodeKind(str, Enum):
    TASK = "task"
    AGENT = "agent"
    TOOL = "tool"
    HUMAN_APPROVAL = "human_approval"


@dataclass(frozen=True)
class WorkflowNode:
    node_id: str
    kind: WorkflowNodeKind
    name: str
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkflowEdge:
    source: str
    target: str
    condition: str = ""


@dataclass(frozen=True)
class WorkflowPlan:
    workflow_id: str
    nodes: List[WorkflowNode] = field(default_factory=list)
    edges: List[WorkflowEdge] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        node_ids = {node.node_id for node in self.nodes}
        if len(node_ids) != len(self.nodes):
            raise ValueError("workflow contains duplicate node ids")
        for edge in self.edges:
            if edge.source not in node_ids:
                raise ValueError("workflow edge source is missing: %s" % edge.source)
            if edge.target not in node_ids:
                raise ValueError("workflow edge target is missing: %s" % edge.target)
        self.topological_nodes()

    def topological_nodes(self) -> List[WorkflowNode]:
        nodes_by_id = {node.node_id: node for node in self.nodes}
        incoming = {node.node_id: 0 for node in self.nodes}
        outgoing: dict[str, list[str]] = {node.node_id: [] for node in self.nodes}
        for edge in self.edges:
            incoming[edge.target] += 1
            outgoing[edge.source].append(edge.target)

        ready = sorted([node_id for node_id, count in incoming.items() if count == 0])
        ordered: List[WorkflowNode] = []
        while ready:
            node_id = ready.pop(0)
            ordered.append(nodes_by_id[node_id])
            for target in sorted(outgoing[node_id]):
                incoming[target] -= 1
                if incoming[target] == 0:
                    ready.append(target)
                    ready.sort()

        if len(ordered) != len(self.nodes):
            raise ValueError("workflow contains a cycle")
        return ordered
