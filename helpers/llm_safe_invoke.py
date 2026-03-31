import time


def safe_llm_invoke(llm, messages, max_retries=3):
    for attempt in range(max_retries):
        # TODO use structured output
        try:
            return llm.invoke(messages)
        except Exception as e:
            if "overloaded" in str(e).lower():
                wait = 2**attempt
                print(f"Retrying LLM call in {wait}s...")
                time.sleep(wait)
            else:
                raise e
    raise Exception("LLM failed after retries")
