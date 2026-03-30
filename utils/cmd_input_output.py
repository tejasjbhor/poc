from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph
import structlog

logger = structlog.get_logger(__name__)


async def send_message(
    graph: CompiledStateGraph,
    session_id: str,
    text: str,
) -> dict:
    config = {"configurable": {"thread_id": session_id}}
    input_state = {"messages": [HumanMessage(content=text)]}

    final_state: dict = {}
    async for chunk in graph.astream(
        input_state,
        config=config,
        stream_mode="updates",
    ):
        for node_name, updates in chunk.items():
            logger.debug(
                "Graph stream: node=%s keys=%s", node_name, list(updates.keys())
            )
        final_state.update(chunk)

    return final_state


async def apply_feedback(
    graph: CompiledStateGraph,
    session_id: str,
    action: str,
    suggestion_id: str | None,
) -> None:
    config = {"configurable": {"thread_id": session_id}}
    await graph.aupdate_state(
        config,
        {
            "sa_feedback": action,
            "sa_card": None,
        },
    )
    logger.info("SA feedback applied: session=%s action=%s", session_id, action)
