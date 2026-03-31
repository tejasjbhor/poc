import json
from langchain_core.tools import StructuredTool

from schemas.search_input_schemas import SearchInput
from tools.agent_tools import search_semantic_scholar


async def semantic_scholar_structured(query: str):
    raw = await search_semantic_scholar.ainvoke({"query": query})
    return json.loads(raw)


semantic_scholar_tool = StructuredTool.from_function(
    name="semantic_scholar_search",
    description="Search Semantic Scholar for academic papers",
    coroutine=semantic_scholar_structured,
    args_schema=SearchInput,
)
