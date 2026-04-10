import asyncio

from registeries.internet_search_unified_tool_registery import INTERNET_SEARCH_TOOLS
from schemas.graphs.internet_search.output import InternetSearchOutput
from state.internet_search_graph import InternetSearchState

tools = INTERNET_SEARCH_TOOLS


async def search_sources_node(state: InternetSearchState, config):
    internet_search_outcome = (
        state.internet_search_outcome or InternetSearchOutput()
    )
    queries = internet_search_outcome.queries
    graph_name = getattr(state.execution_context, "current_graph", None)

    raw_results = {
        "arxiv": [],
        # "semantic_scholar": [],
        # "openalex": [],
        # "crossref": [],
        # "osti": [],
        "web": [],
    }

    # limit queries to avoid explosion
    queries = queries[:6]

    import traceback

    async def run_tool(tool_name: str, tool, query: str):
        try:
            result = await tool.ainvoke({"query": query})

            return tool_name, {
                "query": query,
                "results": result,
            }

        except Exception as e:
            print(f"\n❌ TOOL ERROR [{tool_name}] for query: {query}")
            traceback.print_exc()

            return tool_name, {
                "query": query,
                "results": {
                    "error": "tool_failed",
                    "details": str(e),
                },
            }

    # 🔥 parallel execution across tools AND queries
    tasks = []

    for q in queries:
        for tool_name, tool in tools.items():
            tasks.append(run_tool(tool_name, tool, q))

    results = await asyncio.gather(*tasks)

    # organize results per tool
    for tool_name, payload in results:
        raw_results[tool_name].append(payload)

    return state.model_copy(
        update={
            "raw_results": raw_results,
            "graph_name": graph_name,
        }
    )
