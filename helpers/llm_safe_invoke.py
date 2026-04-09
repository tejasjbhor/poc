import time


def safe_llm_invoke(llm, messages, response_model=None, max_retries=3):
    for attempt in range(max_retries):
        try:
            if response_model:
                structured_llm = llm.with_structured_output(response_model)
                return structured_llm.invoke(messages)

            return llm.invoke(messages)
        except Exception as e:
            if "overloaded" in str(e).lower():
                wait = 2**attempt
                print(f"Retrying LLM call in {wait}s...")
                time.sleep(wait)
            else:
                raise e
    raise Exception("LLM failed after retries")
