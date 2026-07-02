import sys

import uvicorn

from ecomm_agent.rag.vectorstore import build_and_index_default_vector_store


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "index-rag":
        build_and_index_default_vector_store()
        return

    uvicorn.run("ecomm_agent.main:app", host="0.0.0.0", port=8000, reload=False)
