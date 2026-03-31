from tools.internet_search_graph import arxiv_tool, crossref_tool, openalex_tool, osti_tool, semantic_scholar_tool, web_ddg_tool


INTERNET_SEARCH_TOOLS = {
    "arxiv": arxiv_tool,
    "semantic_scholar": semantic_scholar_tool,
    "openalex": openalex_tool,
    "crossref": crossref_tool,
    "osti": osti_tool,
    "web": web_ddg_tool,
}