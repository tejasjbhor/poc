from langgraph.types import interrupt

from state.requirement_generation_graph import RequirementGenerationState


def _build_selection_question(functions: list) -> str:
    lines = ["Select a system function by id (reply with the id only, e.g. f1):", ""]
    for f in functions:
        if not isinstance(f, dict):
            continue
        fid = f.get("id")
        if not fid:
            continue
        name = f.get("name") or ""
        lines.append(f"- {fid}: {name}")
    return "\n".join(lines)


def request_function_selection_node(state: RequirementGenerationState, config):
    
    functions = state.get("system_functions") or []

    if not state.get("selection_prompt"):
        selection_prompt = _build_selection_question(functions)
    else:
        selection_prompt = state["selection_prompt"]

    raw = interrupt(
        {
            "question": selection_prompt,
            "graph_name": config["configurable"]["graph_name"],
        }
    )

    raw_input = (raw.get("raw_user_input") or "").strip()

    valid_ids = {f.get("id") for f in functions if isinstance(f, dict) and f.get("id")} # check id 

    if raw_input not in valid_ids:
        raise ValueError(
            f"Invalid function id {raw_input!r}. Valid: {sorted(valid_ids)}"
        )

    return {
        "selection_prompt": selection_prompt,
        "selected_function_id": raw_input,
        "graph_name": config["configurable"]["graph_name"],
    }
