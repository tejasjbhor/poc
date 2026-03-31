from langchain_core.tools import StructuredTool
import json


from schemas.search_input_schemas import SearchInput
from tools.agent_tools import search_arxiv


async def arxiv_structured(query: str):
    raw = await search_arxiv.ainvoke({"query": query})
    return json.loads(raw)


arxiv_tool = StructuredTool.from_function(
    name="arxiv_search",
    description="Search scientific papers from ArXiv. Returns papers with title, abstract, authors and URL.",
    coroutine=arxiv_structured,
    args_schema=SearchInput,
)
