from pydantic import BaseModel
from typing import List, Literal, Optional

class AgentSpec(BaseModel):
    agent_id: str
    display_name: str
    node_fn_path: str
    entry_node: str
    produces_data: Optional[List] = None
    fixes_data: Optional[List] = None

    type: Literal["graph", "tool"] = "graph"

    default_phase: str = ""
    runs_at_start: bool = False

    description: str = ""