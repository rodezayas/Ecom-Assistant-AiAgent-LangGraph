from pathlib import Path

from langchain_core.embeddings import Embeddings

from ecomm_agent.rag.vectorstore import (
    build_all_rag_documents,
    index_documents,
)


class FakeEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        value = float((sum(ord(char) for char in text) % 1000) + 1)
        return [value, value / 10.0, value / 100.0]


def test_build_all_rag_documents_includes_catalog_and_knowledge_base() -> None:
    documents = build_all_rag_documents()

    source_types = {document.metadata["source_type"] for document in documents}
    assert "product" in source_types
    assert "policy" in source_types
    assert "faq" in source_types
    assert "size_guide" in source_types


def test_index_documents_persists_chroma_collection(tmp_path: Path) -> None:
    documents = build_all_rag_documents()
    vector_store = index_documents(
        documents,
        persist_directory=tmp_path / "vectorstore",
        embeddings=FakeEmbeddings(),
        collection_name="test_collection",
    )

    result = vector_store.similarity_search("running shoes", k=3)
    assert result
    assert any(document.metadata["source_type"] in {"product", "faq", "policy", "size_guide"} for document in result)
