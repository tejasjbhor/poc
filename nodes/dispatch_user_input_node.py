def dispatch_user_input_node(state: dict):
    last_step = state.get("last_step")
    user_input = state.get("raw_user_input")

    # nothing to dispatch
    if not user_input:
        return {}

    updates = {}

    # ---- STEP-BASED MAPPING ----
    if last_step == "ASK_OVERALL_SURFACE_AND_FUNCTION":
        # keep raw input → normalize node will parse it
        updates["raw_user_input"] = user_input

    elif last_step == "COLLECT_PROCESS_LIST":
        updates["process_list_json"] = user_input

    elif last_step == "VALIDATE_PROCESS_LIST":
        updates["process_list_feedback"] = user_input

    elif last_step == "COLLECT_LAYOUT_CONSTRAINTS":
        updates["layout_constraints"] = user_input

    elif last_step == "FINALIZE_APPROVED_LAYOUT":
        updates["layout_json"] = user_input

    # ---- VERY IMPORTANT ----
    # prevent re-processing the same input again
    if last_step == "ASK_OVERALL_SURFACE_AND_FUNCTION":
        updates["raw_user_input"] = user_input  # keep for normalize
    else:
        updates["raw_user_input"] = None

    return updates