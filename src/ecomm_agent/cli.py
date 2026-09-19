"""Command-line interface.

Exposes two entry points:

- ``ecomm-agent index-rag`` -- rebuilds the local Chroma vector store from the
  catalog and knowledge base;
- ``ecomm-agent`` (or ``ecomm-agent-api``) -- starts the Uvicorn server for
  the FastAPI application.
"""

import sys

import uvicorn

from ecomm_agent.rag.vectorstore import build_and_index_default_vector_store


def main() -> None:
    """Parse CLI arguments and dispatch to indexing or the API server."""
    if len(sys.argv) > 1 and sys.argv[1] == "index-rag":
        build_and_index_default_vector_store()
        return
    if len(sys.argv) > 1 and sys.argv[1] == "seed-golden":
        from ecomm_agent.scripts.seed_golden import main as seed_main

        seed_main()
        return
    if len(sys.argv) > 1 and sys.argv[1] == "eval-golden":
        from ecomm_agent.scripts.eval_golden import main as eval_main

        # Pass remaining args (e.g. --limit 2)
        eval_main(sys.argv[2:])
        return

    uvicorn.run("ecomm_agent.main:app", host="0.0.0.0", port=8000, reload=False)
