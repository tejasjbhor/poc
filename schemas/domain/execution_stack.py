from typing import Literal

from pydantic import BaseModel


class ExecutionTask(BaseModel):
    hydration_requester: str
    hydration_resolver: str
    hydration_issues: list[str]
    reasoning: str

    status: Literal["pending", "resolving", "returning"] = "pending"
