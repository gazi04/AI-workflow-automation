from pydantic import BaseModel, Field, model_validator
from typing import Dict, List, Optional

from utils.build_adjacency_list import build_adjacency_list
from workflow.schemas.edges import Edge
from workflow.schemas.workflow_nodes import WorkflowNode
from .ui_metadata_workflow import UIMetadata


class WorkflowDefinition(BaseModel):
    name: str = Field(..., description="A concise, descriptive name for this workflow")
    description: str = Field(
        ..., description="A one-sentence summary of the workflow's purpose"
    )

    start_node_ids: List[str] = Field(
        ...,
        description="List of Node IDs that represent triggers capable of starting this graph.",
    )

    nodes: Dict[str, WorkflowNode] = Field(
        ...,
        description="A dictionary mapping node_id to the Node object for O(1) lookups.",
    )
    edges: List[Edge] = Field(
        default_factory=list, description="Flat list of edges connecting the nodes."
    )

    ui_metadata: Optional[UIMetadata] = None

    @model_validator(mode="after")
    def check_for_cycles(self) -> "WorkflowDefinition":
        """
        Uses Depth-First Search to ensure the graph is a
        Directed Acyclic Graph (DAG).
        """
        if not self.edges:
            return self

        adj_list = build_adjacency_list(self.edges)

        visited = set()  # Nodes fully processed
        rec_stack = set()  # Nodes currently in the recursion stack

        def has_cycle(node_id: str) -> bool:
            visited.add(node_id)
            rec_stack.add(node_id)

            for edge in adj_list.get(node_id, []):
                neighbor_id = edge.target
                if neighbor_id not in visited:
                    if has_cycle(neighbor_id):
                        return True
                elif neighbor_id in rec_stack:
                    # Found a back-edge to a node currently being explored
                    return True

            rec_stack.remove(node_id)
            return False

        for start_node in self.start_node_ids:
            if start_node not in visited:
                if has_cycle(start_node):
                    raise ValueError(
                        f"Circular dependency detected starting from node '{start_node}'. "
                        "Workflows must be Directed Acyclic Graphs (DAGs)."
                    )

        return self
