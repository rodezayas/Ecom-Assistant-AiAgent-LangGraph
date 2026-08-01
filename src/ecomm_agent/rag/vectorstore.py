"""Chroma vector store: document building, indexing, and loading.

Builds RAG documents from the catalog JSON and the Markdown knowledge base,
indexes them into a local persisted Chroma collection, and loads the
collection for retrieval. Each chunk carries explicit metadata (``source_type``,
``category``, ``product_id``/``section``) so retrieval can be filtered before
similarity search.

The vector store is optional: when it has not been indexed, the retrieval
service transparently falls back to lexical matching.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

from ecomm_agent.core.config import settings
from ecomm_agent.schemas.catalog import Product
from ecomm_agent.services.catalog import load_catalog


@dataclass(frozen=True)
class RAGDocument:
    """A single document chunk ready for indexing.

    ``content`` is the chunk text; ``metadata`` carries the structured fields
    used for retrieval filtering (e.g. ``source_type``, ``product_id``).
    """

    content: str
    """The chunk text to embed and search."""

    metadata: dict[str, str]
    """Structured metadata attached to the chunk."""


def build_product_document(product: Product) -> str:
    """Build the embedding text for a product.

    Joins name, description, category, and tags into a single rich text
    string. Size, color, and stock are intentionally excluded -- they are
    queried deterministically from the catalog after retrieval.

    Args:
        product: The product to serialize.

    Returns:
        The product's document text.
    """
    return " | ".join(
        [
            product.name,
            product.description,
            product.category,
            ", ".join(product.tags),
        ]
    )


def build_product_rag_document(product: Product) -> RAGDocument:
    """Build a RAG document for a single product.

    Args:
        product: The product to index.

    Returns:
        A :class:`RAGDocument` with ``source_type=product`` and the product id
        in metadata.
    """
    return RAGDocument(
        content=build_product_document(product),
        metadata={
            "source_type": "product",
            "category": product.category,
            "product_id": product.id,
        },
    )


def _split_markdown_sections(text: str) -> list[tuple[str, str]]:
    """Split Markdown text into ``##``-delimited sections.

    Each ``##`` header starts a new chunk; body lines accumulate until the
    next header. Top-level ``#`` titles are treated as document headers, not
    chunks.

    Args:
        text: The Markdown source text.

    Returns:
        A list of ``(title, body)`` pairs, one per section.
    """
    sections: list[tuple[str, str]] = []
    current_title: str | None = None
    current_lines: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            if current_title and current_lines:
                sections.append((current_title, " ".join(current_lines).strip()))
            current_title = line.removeprefix("## ").strip()
            current_lines = []
            continue
        if line and not line.startswith("# "):
            current_lines.append(line)

    if current_title and current_lines:
        sections.append((current_title, " ".join(current_lines).strip()))

    return sections


def build_markdown_rag_documents(
    path: str | Path,
    *,
    source_type: str,
    category_slug: str,
) -> list[RAGDocument]:
    """Build RAG documents from a Markdown file, one per section.

    Args:
        path: Path to the Markdown file.
        source_type: Metadata source type (e.g. ``policy``, ``faq``).
        category_slug: Metadata category (e.g. ``store_policy``).

    Returns:
        A list of :class:`RAGDocument` objects; empty when the file does not
        exist.
    """
    markdown_path = Path(path)
    if not markdown_path.exists():
        return []

    text = markdown_path.read_text(encoding="utf-8")
    sections = _split_markdown_sections(text)
    return [
        RAGDocument(
            content=f"{title}\n\n{body}",
            metadata={
                "source_type": source_type,
                "category": category_slug,
                "section": title.lower().replace(" ", "_"),
            },
        )
        for title, body in sections
    ]


def build_catalog_rag_documents(products: list[Product]) -> list[RAGDocument]:
    """Build product RAG documents for a catalog.

    Args:
        products: Catalog products to index.

    Returns:
        A list of :class:`RAGDocument` objects, one per product.
    """
    return [build_product_rag_document(product) for product in products]


def build_knowledge_base_rag_documents(knowledge_base_dir: str | Path) -> list[RAGDocument]:
    """Build RAG documents from the Markdown knowledge base.

    Reads ``policies.md``, ``faq.md``, and ``size_guide.md`` from the given
    directory, each under its own source type.

    Args:
        knowledge_base_dir: Directory containing the Markdown knowledge files.

    Returns:
        A list of :class:`RAGDocument` objects from all knowledge files.
    """
    base_dir = Path(knowledge_base_dir)
    return [
        *build_markdown_rag_documents(
            base_dir / "policies.md",
            source_type="policy",
            category_slug="store_policy",
        ),
        *build_markdown_rag_documents(
            base_dir / "faq.md",
            source_type="faq",
            category_slug="brand_faq",
        ),
        *build_markdown_rag_documents(
            base_dir / "size_guide.md",
            source_type="size_guide",
            category_slug="fit_and_sizing",
        ),
    ]


def build_all_rag_documents() -> list[RAGDocument]:
    """Build every RAG document: catalog products plus the knowledge base.

    Returns:
        A list of all product, policy, FAQ, and size-guide documents.
    """
    catalog = load_catalog(settings.catalog_path)
    return [
        *build_catalog_rag_documents(catalog),
        *build_knowledge_base_rag_documents(settings.knowledge_base_dir),
    ]


def to_langchain_documents(documents: list[RAGDocument]) -> list[Document]:
    """Convert :class:`RAGDocument` objects to LangChain ``Document`` objects.

    Args:
        documents: RAG documents to convert.

    Returns:
        The equivalent LangChain documents.
    """
    return [
        Document(
            page_content=document.content,
            metadata=document.metadata,
        )
        for document in documents
    ]


def build_embeddings() -> OpenAIEmbeddings:
    """Build the OpenAI embedding function used for indexing and search.

    Returns:
        An :class:`OpenAIEmbeddings` instance configured from settings.
    """
    return OpenAIEmbeddings(
        model=settings.openai_embedding_model,
        api_key=settings.openai_api_key,
    )


def index_documents(
    documents: list[RAGDocument],
    *,
    persist_directory: str | Path,
    embeddings: Embeddings,
    collection_name: str = "ecomm_knowledge",
) -> Chroma:
    """Index documents into a persisted Chroma collection.

    Any existing documents in the collection are deleted first so reindexing
    does not accumulate stale chunks. Document ids are derived from the source
    type and chunk index.

    Args:
        documents: RAG documents to index.
        persist_directory: Directory where Chroma persists the collection.
        embeddings: Embedding function to use.
        collection_name: Name of the Chroma collection.

    Returns:
        The populated :class:`Chroma` vector store.
    """
    persist_path = Path(persist_directory)
    persist_path.mkdir(parents=True, exist_ok=True)

    vector_store = Chroma(
        collection_name=collection_name,
        persist_directory=str(persist_path),
        embedding_function=embeddings,
    )
    langchain_documents = to_langchain_documents(documents)

    if langchain_documents:
        existing = vector_store.get(include=[])
        existing_ids = existing.get("ids", [])
        if existing_ids:
            vector_store.delete(ids=existing_ids)

        ids = [
            f"{document.metadata['source_type']}:{index}"
            for index, document in enumerate(documents)
        ]
        vector_store.add_documents(documents=langchain_documents, ids=ids)

    return vector_store


def build_and_index_default_vector_store() -> Chroma:
    """Build all documents and index them into the configured vector store.

    Uses the catalog and knowledge base from settings and the configured
    embeddings. Intended to be run via the ``index-rag`` CLI command.

    Returns:
        The populated :class:`Chroma` vector store.
    """
    documents = build_all_rag_documents()
    embeddings = build_embeddings()
    return index_documents(
        documents,
        persist_directory=settings.vector_store_path,
        embeddings=embeddings,
    )


def load_vector_store(
    *,
    persist_directory: str | Path | None = None,
    collection_name: str = "ecomm_knowledge",
    embeddings: Embeddings | None = None,
) -> Chroma | None:
    """Load an existing persisted Chroma collection.

    Args:
        persist_directory: Collection directory; defaults to the configured
            ``VECTOR_STORE_PATH``.
        collection_name: Name of the Chroma collection.
        embeddings: Embedding function to use; defaults to the configured
            OpenAI embeddings.

    Returns:
        The :class:`Chroma` store, or ``None`` when the persist directory does
        not exist (i.e. the store has not been indexed yet).
    """
    persist_path = Path(persist_directory or settings.vector_store_path)
    if not persist_path.exists():
        return None

    embedding_function = embeddings or build_embeddings()
    return Chroma(
        collection_name=collection_name,
        persist_directory=str(persist_path),
        embedding_function=embedding_function,
    )
