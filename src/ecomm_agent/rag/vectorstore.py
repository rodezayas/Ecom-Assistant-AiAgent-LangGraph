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
    content: str
    metadata: dict[str, str]


def build_product_document(product: Product) -> str:
    return " | ".join(
        [
            product.name,
            product.description,
            product.category,
            ", ".join(product.tags),
        ]
    )


def build_product_rag_document(product: Product) -> RAGDocument:
    return RAGDocument(
        content=build_product_document(product),
        metadata={
            "source_type": "product",
            "category": product.category,
            "product_id": product.id,
        },
    )


def _split_markdown_sections(text: str) -> list[tuple[str, str]]:
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
    return [build_product_rag_document(product) for product in products]


def build_knowledge_base_rag_documents(knowledge_base_dir: str | Path) -> list[RAGDocument]:
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
    catalog = load_catalog(settings.catalog_path)
    return [
        *build_catalog_rag_documents(catalog),
        *build_knowledge_base_rag_documents(settings.knowledge_base_dir),
    ]


def to_langchain_documents(documents: list[RAGDocument]) -> list[Document]:
    return [
        Document(
            page_content=document.content,
            metadata=document.metadata,
        )
        for document in documents
    ]


def build_embeddings() -> OpenAIEmbeddings:
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
    persist_path = Path(persist_directory or settings.vector_store_path)
    if not persist_path.exists():
        return None

    embedding_function = embeddings or build_embeddings()
    return Chroma(
        collection_name=collection_name,
        persist_directory=str(persist_path),
        embedding_function=embedding_function,
    )
