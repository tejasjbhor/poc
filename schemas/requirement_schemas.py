from typing import TypedDict


class GeneratedRequirement(TypedDict, total=False):
    id: str
    function_id: str
    title: str
    statement: str
    rationale: str
    priority: str
    category: str
