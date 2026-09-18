"""Guardrail node.

Evaluates the user message against the deterministic guardrail layer before
any LLM generation happens. The allowed vocabulary is derived once at import
time from the catalog and the knowledge base.
"""

from ecomm_agent.agents.state import AgentState
from ecomm_agent.core.config import settings
from ecomm_agent.observability.tracing import get_tracer, is_content_recording_enabled
from ecomm_agent.rag.vectorstore import build_knowledge_base_rag_documents
from ecomm_agent.services.catalog import load_catalog
from ecomm_agent.services.guardrails import (
    build_allowed_vocabulary,
    evaluate_message_guardrails,
)

tracer = get_tracer(__name__)


# Source-of-truth catalog loaded once at import time.
CATALOG = load_catalog(settings.catalog_path)
# Knowledge-base documents loaded once at import time.
KNOWLEDGE_DOCUMENTS = build_knowledge_base_rag_documents(settings.knowledge_base_dir)
# Vocabulary of every word the store legitimately talks about, built once from
# the source-of-truth catalog and knowledge documents.
ALLOWED_VOCABULARY = build_allowed_vocabulary(
    CATALOG,
    extra_texts=[document.content for document in KNOWLEDGE_DOCUMENTS],
)


def guardrails_node(state: AgentState) -> AgentState:
    """Apply the deterministic guardrails to the user message.

    Args:
        state: Agent state containing ``user_message``.

    Returns:
        A copy of the state. If the message is allowed, the guardrail flags
        are cleared; otherwise ``guardrail_blocked`` is set with the reason
        and matched terms, and the intent is forced to ``out_of_domain`` for
        out-of-scope messages.
    """
    with tracer.start_as_current_span("guardrails") as span:
        result = evaluate_message_guardrails(
            text=state.user_message,
            allowed_vocabulary=ALLOWED_VOCABULARY,
        )
        if result.allowed:
            new_state = state.model_copy(
                update={
                    "guardrail_blocked": False,
                    "guardrail_reason": None,
                    "blocked_terms": [],
                }
            )
        else:
            new_state = state.model_copy(
                update={
                    "guardrail_blocked": True,
                    "guardrail_reason": result.reason,
                    "blocked_terms": list(result.matched_terms),
                    "intent": "out_of_domain" if result.reason == "out_of_scope" else state.intent,
                }
            )
        try:
            span.set_attribute("thread_id", state.thread_id)
            span.set_attribute("guardrail.blocked", new_state.guardrail_blocked)
            span.set_attribute("guardrail.reason", new_state.guardrail_reason or "")
            span.set_attribute("guardrail.blocked_terms", ",".join(new_state.blocked_terms[:5]))
            span.set_attribute("intent", new_state.intent or "")
            if is_content_recording_enabled():
                span.set_attribute("input.value", state.user_message[:2000])
                span.set_attribute("output.value", new_state.guardrail_reason or "allowed")
        except Exception:
            pass
        return new_state
