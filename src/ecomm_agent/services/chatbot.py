from ecomm_agent.agents.graph import build_graph
from ecomm_agent.agents.state import AgentState
from ecomm_agent.services.llm import generate_response_text


GRAPH = build_graph()


def process_user_message(thread_id: str, text: str) -> AgentState:
    state = AgentState(thread_id=thread_id, user_message=text)
    result = GRAPH.invoke(state)
    if isinstance(result, AgentState):
        return result
    return AgentState.model_validate(result)


async def build_reply_text(state: AgentState) -> str:
    llm_response = await generate_response_text(state)
    if llm_response:
        return llm_response

    return state.response_text or (
        "I can help with verified Nova Style products, prices, colors, sizes, and stock."
    )
