def normalize_interrupts(interrupts, seen_interrupt_ids=None):
    if not interrupts:
        return None

    interrupt_ids = [i.id for i in interrupts]

    # =========================
    # DEDUPLICATION
    # =========================
    if seen_interrupt_ids is not None:
        for iid in interrupt_ids:
            if iid in seen_interrupt_ids:
                return None  # already processed

        for iid in interrupt_ids:
            seen_interrupt_ids.add(iid)

    # =========================
    # FORMAT OUTPUT
    # =========================
    data = []
    graph_name = None

    for i in interrupts:
        graph_name = i.value.get("graph_name")
        data.append({"id": i.id, "value": i.value.get("question")})

    return {
        "type": "interrupt",
        "graph_name": graph_name,
        "data": data,
    }
