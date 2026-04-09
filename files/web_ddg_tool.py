from langchain_core.tools import StructuredTool
import json


from schemas.search_input_schemas import SearchInput
from tools.agent_tools import search_web_ddg


async def web_structured(query: str):
    raw = await search_web_ddg(query)
    return json.loads(raw)


web_ddg_tool = StructuredTool.from_function(
    name="web_search",
    description="Search the web using DuckDuckGo",
    coroutine=web_structured,
    args_schema=SearchInput,
)
