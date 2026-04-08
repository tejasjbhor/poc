def ws_to_json_safe(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump()

    if isinstance(obj, dict):
        return {k: ws_to_json_safe(v) for k, v in obj.items()}

    if isinstance(obj, list):
        return [ws_to_json_safe(v) for v in obj]

    return obj
