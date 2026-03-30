import json

from langchain.messages import HumanMessage, SystemMessage

from helpers.llm_safe_invoke import safe_llm_invoke
from prompts.system_definition_prompts import SYSTEM_DEFINITION_PROMPTS
from state.system_definition_graph import SystemDefinitionState


def finalize_system_definition_node(state: SystemDefinitionState, llm):
    prompt = SYSTEM_DEFINITION_PROMPTS["prompt_finalize_system_definition"]

    response = safe_llm_invoke(
        llm,
        [
            SystemMessage(content=prompt),
            HumanMessage(
                content=json.dumps(
                    {
                        "system_functions_json": state.get("system_functions_json"),
                        "user_approval": state.get("approval_status", {}),
                    }
                )
            ),
        ],
    )

    content = response.content.strip()

    if content == "SYSTEM_NOT_APPROVED":
        return {
            "last_step": "FINALIZE_SYSTEM_DEFINITION",
        }

    return {
        "messages": [response],
        "final_system_definition": content,
        "last_step": "FINALIZE_SYSTEM_DEFINITION",
    }
