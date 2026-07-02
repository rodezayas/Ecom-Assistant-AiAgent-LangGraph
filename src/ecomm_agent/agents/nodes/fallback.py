from ecomm_agent.agents.state import AgentState


def fallback_node(state: AgentState) -> AgentState:
    return state.model_copy(
        update={
            "response_text": "I could not fulfill that request with verified catalog data."
        }
    )
