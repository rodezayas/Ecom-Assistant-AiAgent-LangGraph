"""Retrieval service.

Unified entry point for product and knowledge retrieval. Tries semantic
retrieval through the persisted Chroma vector store first and falls back to
deterministic lexical matching when the vector store is unavailable or
unindexed. Verified products are always resolved back through the catalog
source of truth.
"""

from __future__ import annotations

from langchain_core.documents import Document

from ecomm_agent.agents.state import KnowledgeSnippet
from ecomm_agent.core.config import settings
from ecomm_agent.rag.vectorstore import build_knowledge_base_rag_documents, load_vector_store
from ecomm_agent.schemas.catalog import Product
from ecomm_agent.services.catalog import extract_search_filters, load_catalog, search_catalog
from ecomm_agent.services.guardrails import tokenize


CATALOG = load_catalog(settings.catalog_path)
"""Catalog loaded once at import time from the configured path."""

PRODUCT_LOOKUP = {product.id: product for product in CATALOG}
"""Maps product ids to :class:`Product` objects for fast resolution."""

KNOWLEDGE_DOCUMENTS = build_knowledge_base_rag_documents(settings.knowledge_base_dir)
"""Knowledge-base documents built once at import time for lexical fallback."""


def _query_vector_store(
    query: str,
    *,
    source_type: str,
    limit: int,
) -> list[Document]:
    """Run a similarity search against the persisted Chroma store.

    Args:
        query: The user query text.
        source_type: Metadata filter (``product``, ``policy``, ``faq``, or
            ``size_guide``).
        limit: Maximum number of documents to return.

    Returns:
        The matching documents, or an empty list when the vector store has
        not been indexed.
    """
    vector_store = load_vector_store()
    if vector_store is None:
        return []
    return vector_store.similarity_search(
        query,
        k=limit,
        filter={"source_type": source_type},
    )


def retrieve_products(query: str, *, limit: int = 3) -> tuple[list[Product], str | None, str | None, str | None, float | None]:
    """Retrieve products matching a free-text query.

    Semantic retrieval is attempted first; retrieved ids are resolved against
    the catalog and filtered by the extracted deterministic filters, then
    re-ranked lexically. If semantic retrieval yields nothing (or the vector
    store is unavailable), a full lexical catalog search is performed.

    Args:
        query: The user query text.
        limit: Maximum number of products to return.

    Returns:
        A tuple of ``(products, category, color, size, price_ceiling)`` where
        the filters are those extracted from the query.
    """
    filters = extract_search_filters(query, CATALOG)
    try:
        documents = _query_vector_store(query, source_type="product", limit=limit * 4)
    except Exception:
        documents = []

    if documents:
        products: list[Product] = []
        for document in documents:
            product_id = document.metadata.get("product_id")
            product = PRODUCT_LOOKUP.get(product_id)
            if not product:
                continue
            if filters.category and product.category != filters.category:
                continue
            if filters.price_ceiling is not None and product.price > filters.price_ceiling:
                continue
            if product not in products:
                products.append(product)

        if products:
            lexical_products, _ = search_catalog(query, products, limit=limit)
            if lexical_products:
                return (
                    lexical_products,
                    filters.category,
                    filters.color,
                    filters.size,
                    filters.price_ceiling,
                )

    lexical_products, _ = search_catalog(query, CATALOG, limit=limit)
    return (
        lexical_products,
        filters.category,
        filters.color,
        filters.size,
        filters.price_ceiling,
    )


def retrieve_knowledge(query: str, *, limit: int = 3) -> list[KnowledgeSnippet]:
    """Retrieve knowledge-base snippets matching a free-text query.

    Tries semantic retrieval per source type (policy, FAQ, size guide); when
    nothing is retrieved, falls back to lexical token-overlap scoring over the
    knowledge documents.

    Args:
        query: The user query text.
        limit: Maximum number of snippets to return.

    Returns:
        A list of :class:`KnowledgeSnippet` objects, ordered by relevance.
    """
    source_types = ("policy", "faq", "size_guide")
    snippets: list[KnowledgeSnippet] = []

    for source_type in source_types:
        try:
            documents = _query_vector_store(query, source_type=source_type, limit=1)
        except Exception:
            documents = []

        for document in documents:
            snippets.append(
                KnowledgeSnippet(
                    source_type=document.metadata.get("source_type", source_type),
                    category=document.metadata.get("category", ""),
                    section=document.metadata.get("section"),
                    content=document.page_content,
                )
            )

    if snippets:
        return snippets[:limit]

    query_tokens = {
        token
        for token in tokenize(query)
        if len(token) > 2
    }
    scored_documents: list[tuple[int, KnowledgeSnippet]] = []
    for document in KNOWLEDGE_DOCUMENTS:
        content_tokens = set(tokenize(document.content))
        score = sum(1 for token in query_tokens if token in content_tokens)
        if score <= 0:
            continue
        scored_documents.append(
            (
                score,
                KnowledgeSnippet(
                    source_type=document.metadata.get("source_type", ""),
                    category=document.metadata.get("category", ""),
                    section=document.metadata.get("section"),
                    content=document.content,
                ),
            )
        )

    scored_documents.sort(key=lambda item: -item[0])
    return [snippet for _, snippet in scored_documents[:limit]]
