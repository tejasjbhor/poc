from pydantic import BaseModel

from registeries.agent_registry import AgentRegistry
from schemas.agents.agent_spec import AgentSpec
from schemas.graphs.layout.output import LayoutOutput
from schemas.graphs.system_definition.output import SystemDefinitionOutput


def get_model_fields(model_cls: type[BaseModel]) -> set[str]:
    return set(model_cls.model_fields.keys())


def create_agents_registry() -> AgentRegistry:
    registry = AgentRegistry()

    registry.register(
        AgentSpec(
            agent_id="system_definition",
            display_name="System Definition",
            node_fn_path="graphs.system_definition_graph.build_system_definition_graph",
            default_phase="phase_layout",
            runs_at_start=False,
            description="Getting system description and functions from user.",
            entry_node="EXECUTION_CONTEXT_DEFINITION",
            produces_data=get_model_fields(SystemDefinitionOutput),
            fixes_data=get_model_fields(SystemDefinitionOutput),
        )
    )

    registry.register(
        AgentSpec(
            agent_id="internet_search",
            display_name="Internet Search Agent",
            node_fn_path="graphs.internet_search_graph.build_internet_search_graph",
            default_phase="phase_layout",
            runs_at_start=False,
            description="Searching the internet for a particular system.",
            entry_node="EXECUTION_CONTEXT_DEFINITION",
        )
    )

    registry.register(
        AgentSpec(
            agent_id="layout",
            display_name="Layout Agent",
            node_fn_path="graphs.layout_graph.build_facility_layout_graph",
            default_phase="phase_layout",
            runs_at_start=False,
            description="Generate a 2D layout for a given system.",
            entry_node="EXECUTION_CONTEXT_DEFINITION",
            produces_data=get_model_fields(LayoutOutput),
            fixes_data=get_model_fields(LayoutOutput),
        )
    )

    return registry
