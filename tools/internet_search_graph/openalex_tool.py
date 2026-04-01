from langchain_core.tools import StructuredTool
import json

from schemas.search_input_schemas import SearchInput
from tools.agent_tools import search_openalex


async def openalex_structured(query: str):
    raw = await search_openalex({"query": query})
    return json.loads(raw)


openalex_tool = StructuredTool.from_function(
    name="openalex_search",
    description="Search OpenAlex for academic works and publications",
    coroutine=openalex_structured,
    args_schema=SearchInput,
)
