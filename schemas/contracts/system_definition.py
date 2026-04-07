from typing import List, TypedDict

from schemas.system_schemas import SystemFunction


class SystemDefinition(TypedDict):
    system_description: str
    system_functions: List[SystemFunction]
    assumptions: List[str]