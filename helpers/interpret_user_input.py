DONE_KEYWORDS = {
    "ok",
    "done",
    "finish",
    "finished",
    "that's fine",
    "looks good",
    "good",
    "approve",
    "confirm",
    "yes that's correct",
}


def is_done_user_input(text: str) -> bool:
    if not text:
        return False

    text_lower = text.strip().lower()

    return any(k in text_lower for k in DONE_KEYWORDS)
