def serialize_interrupt(update):
    if "__interrupt__" in update:
        interrupts = update["__interrupt__"]

        return {"__interrupt__": [{"value": i.value, "id": i.id} for i in interrupts]}

    return update
