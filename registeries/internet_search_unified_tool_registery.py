from tools.internet_search_graph.arxiv_tool import arxiv_tool
from tools.internet_search_graph.semantic_scholar_tool import semantic_scholar_tool
from tools.internet_search_graph.openalex_tool import openalex_tool
from tools.internet_search_graph.crossref_tool import crossref_tool
from tools.internet_search_graph.osti_tool import osti_tool
from tools.internet_search_graph.web_ddg_tool import web_ddg_tool


INTERNET_SEARCH_TOOLS = {
    "arxiv": arxiv_tool,
    # "semantic_scholar": semantic_scholar_tool,
    # "openalex": openalex_tool,
    # "crossref": crossref_tool,
    # "osti": osti_tool,
    "web": web_ddg_tool,
}
