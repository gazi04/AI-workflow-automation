from pydantic import BaseModel, Field
from typing import Dict, List, Optional

from workflow.schemas.edges import Edge
from workflow.schemas.workflow_nodes import WorkflowNode
from .ui_metadata_workflow import UIMetadata


class WorkflowDefinition(BaseModel):
    name: str = Field(..., description="A concise, descriptive name for this workflow")
    description: str = Field(
        ..., description="A one-sentence summary of the workflow's purpose"
    )

    start_node_ids: List[str] = Field(
        ..., description="List of Node IDs that represent triggers capable of starting this graph."
    )
    
    nodes: Dict[str, WorkflowNode] = Field(
        ..., description="A dictionary mapping node_id to the Node object for O(1) lookups."
    )
    edges: List[Edge] = Field(
        default_factory=list, description="Flat list of edges connecting the nodes."
    )

    ui_metadata: Optional[UIMetadata] = None
