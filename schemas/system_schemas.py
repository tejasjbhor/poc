from typing import TypedDict, List


class SystemFunctionInterface(TypedDict, total=False):
    function_id: str
    materials: List[str]


class SystemFunction(TypedDict, total=False):
    id: str
    name: str
    description: str
    surface_area: float
    category: str
    interfaces_in: List[SystemFunctionInterface]
    interfaces_out: List[SystemFunctionInterface]
