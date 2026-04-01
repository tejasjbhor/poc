from langchain_core.tools import StructuredTool
import json


from schemas.search_input_schemas import SearchInput
from tools.agent_tools import search_crossref


async def crossref_structured(query: str):
    raw = await search_crossref({"query": query})
    return json.loads(raw)


crossref_tool = StructuredTool.from_function(
    name="crossref_search",
    description="Search Crossref for publications and DOIs",
    coroutine=crossref_structured,
    args_schema=SearchInput,
)
