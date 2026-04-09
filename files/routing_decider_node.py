from state.overall_observer_graph import OverallObserverState
from langgraph.types import interrupt


def routing_decider_node(state: OverallObserverState, config, llm):

    question = """**Hey! 👋**

    What would you like to do today?

    **1. Define system of interest**
    **2. Perform advanced web search for a certain functionality**
    **3. Create a 2D layout of the system**

    ➡️ *Please pick one to proceed.*
"""
    user_input = interrupt(
        {"question": question, "graph_name": config["configurable"]["graph_name"]}
    )
    next_step = None

    match user_input["raw_user_input"].strip():
        case "1":
            next_step = "SYSTEM_DEFINITION"
        case "2":
            next_step = "INTERNET_SEARCH"
        case "3":
            next_step = "LAYOUT"
        case _:
            next_step = None

    return {
        "last_step": state.get("step"),
        "step": state.get("next_step"),
        "next_step": next_step,
        "graph_name": config["configurable"]["graph_name"],
    }
