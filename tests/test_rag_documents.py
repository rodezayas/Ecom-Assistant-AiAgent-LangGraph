from ecomm_agent.core.config import settings
from ecomm_agent.rag.vectorstore import (
    build_markdown_rag_documents,
    build_product_rag_document,
)
from ecomm_agent.services.catalog import load_catalog


def test_product_rag_document_has_expected_metadata() -> None:
    product = load_catalog(settings.catalog_path)[0]
    document = build_product_rag_document(product)

    assert document.metadata["source_type"] == "product"
    assert document.metadata["category"] == product.category
    assert document.metadata["product_id"] == product.id
    assert product.name in document.content


def test_policy_markdown_is_split_into_sections() -> None:
    documents = build_markdown_rag_documents(
        "data/knowledge/policies.md",
        source_type="policy",
        category_slug="store_policy",
    )

    assert len(documents) >= 3
    assert all(document.metadata["source_type"] == "policy" for document in documents)
    assert any("Shipping" in document.content for document in documents)


def test_faq_markdown_is_split_into_sections() -> None:
    documents = build_markdown_rag_documents(
        "data/knowledge/faq.md",
        source_type="faq",
        category_slug="brand_faq",
    )

    assert len(documents) >= 3
    assert all(document.metadata["source_type"] == "faq" for document in documents)


def test_size_guide_markdown_is_split_into_sections() -> None:
    documents = build_markdown_rag_documents(
        "data/knowledge/size_guide.md",
        source_type="size_guide",
        category_slug="fit_and_sizing",
    )

    assert len(documents) >= 3
    assert all(document.metadata["source_type"] == "size_guide" for document in documents)
