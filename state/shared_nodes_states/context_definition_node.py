from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


class ExecutionContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["standalone", "subgraph", "resume", "batch"] = "standalone"
    source: Literal["user", "graph", "resume", "system"] = "system"

    parent_graph: Optional[str] = None
    current_graph: Optional[str] = None
    previous_graph: Optional[str] = None
    root_graph: Optional[str] = None

    depth: int = 0
    run_id: Optional[str] = None
