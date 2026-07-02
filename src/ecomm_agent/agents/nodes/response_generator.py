from ecomm_agent.agents.state import AgentState


def response_generator_node(state: AgentState) -> AgentState:
    return state.model_copy(
        update={
            "response_text": "Agent scaffold initialized. Product logic will be added in the next phase."
        }
    )
