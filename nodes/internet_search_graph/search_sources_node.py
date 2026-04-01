import asyncio
import traceback

from state.internet_search_graph import InternetSearchState


async def search_sources_node(state: InternetSearchState, tools):
    queries = state.get("queries", [])

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

    return {
        "raw_results": raw_results,
        "step": "EXTRACT_CANDIDATES",
    }
