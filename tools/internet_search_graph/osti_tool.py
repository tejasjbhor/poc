from langchain_core.tools import StructuredTool
import json


from schemas.search_input_schemas import SearchInput
from tools.agent_tools import search_osti


async def osti_structured(query: str):
    raw = await search_osti.ainvoke({"query": query})
    return json.loads(raw)


osti_tool = StructuredTool.from_function(
    name="osti_search",
    description="Search OSTI.gov for scientific and technical reports",
    coroutine=osti_structured,
    args_schema=SearchInput,
)
