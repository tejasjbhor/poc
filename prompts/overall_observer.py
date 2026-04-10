OVERALL_OBSERVER_PROMPTS = {
    "generate_welcome_message": """
You are an assistant helping a user choose what to do.

Available actions:
{agent_descriptions}

Generate a friendly welcome message that:
- greets the user
- clearly lists the options as numbered choices
- encourages the user to pick one

Keep it concise and clear.
""".strip(),
    "pick_data_fixer_agent": """
You are a routing engine for a multi-agent system.

Your task: decide which agent(s) should handle missing data requirements.

---

## HYDRATION ISSUES
{hydration_issues}

---

## AVAILABLE AGENTS (YOU MUST SELECT ONLY FROM THESE)
{agents}

---

## RULES
- You MUST select only from the provided agents
- You may select multiple agents if needed
- Match issues to agents based on capability overlap
- Prefer minimal number of agents
- Explain your reasoning clearly

---

## OUTPUT FORMAT (STRICT JSON)
{
    "agent_id": "agent_id",
    "reasoning": "explanation of decision"
}
""",
}
