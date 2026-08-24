from typing import Literal, Optional
from pydantic import BaseModel, Field

# The named source handles a node can route through. `None` is the implicit
# success path every trigger/action node carries; conditions route through
# true_path/false_path; any node that can fail routes through error_path.
SourceHandle = Literal["true_path", "false_path", "error_path"]

ERROR_HANDLE: SourceHandle = "error_path"


class Edge(BaseModel):
    id: str
    source: str
    target: str
    sourceHandle: Optional[SourceHandle] = Field(
        default=None,
        description=(
            "Named outgoing handle. 'true_path'/'false_path' route a condition "
            "node; 'error_path' routes a node's failure to its error handler. "
            "None is the default success path."
        ),
    )
    targetHandle: Optional[str] = None
