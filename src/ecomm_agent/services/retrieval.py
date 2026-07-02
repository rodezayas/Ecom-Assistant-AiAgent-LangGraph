from __future__ import annotations

from langchain_core.documents import Document

from ecomm_agent.agents.state import KnowledgeSnippet
from ecomm_agent.core.config import settings
from ecomm_agent.rag.vectorstore import build_knowledge_base_rag_documents, load_vector_store
from ecomm_agent.schemas.catalog import Product
from ecomm_agent.services.catalog import extract_search_filters, load_catalog, search_catalog
from ecomm_agent.services.guardrails import tokenize


CATALOG = load_catalog(settings.catalog_path)
PRODUCT_LOOKUP = {product.id: product for product in CATALOG}
KNOWLEDGE_DOCUMENTS = build_knowledge_base_rag_documents(settings.knowledge_base_dir)


def _query_vector_store(
    query: str,
    *,
    source_type: str,
    limit: int,
) -> list[Document]:
    vector_store = load_vector_store()
    if vector_store is None:
        return []
    return vector_store.similarity_search(
        query,
        k=limit,
        filter={"source_type": source_type},
    )


def retrieve_products(query: str, *, limit: int = 3) -> tuple[list[Product], str | None, str | None, str | None, float | None]:
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
