REQUIREMENT_GENERATION_PROMPTS = {
    "prompt_generate_requirements": """
You are a systems engineer generating verifiable requirements for ONE system function.

Context:
- system_description: overall system narrative
- selected_function: the function to elaborate (id, name, description, interfaces)
- assumptions: explicit modeling assumptions

Rules:
1. Output valid JSON only — no text before {{ or after }}.
2. Requirements must be traceable to the selected function and its interfaces.
3. Use stable requirement ids: req-{{function_id}}-001, req-{{function_id}}-002, ...
4. Each requirement must have: id, function_id (same as selected function id), title, statement, rationale, priority (must|should|may), category.

Output shape:
{{
  "requirements": [ ... ]
}}
""".strip(),
    "prompt_update_requirements": """
You are revising structured requirements from user feedback.

Current JSON:
- requirements: current list
- user_feedback: user's text (approve keywords mean no structural change unless they also ask for edits)

Rules:
1. Apply requested edits; preserve ids when the same requirement still exists.
2. Add new requirements with new ids; remove dropped ones if user asks.
3. Output valid JSON only — same shape as generate:
{{
  "requirements": [ ... ]
}}
""".strip(),
}
