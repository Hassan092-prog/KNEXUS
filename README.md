# KNEXUS: Knowledge Network for EXploration and Unified Services

KNEXUS is an intelligent, agent-driven knowledge management and retrieval platform designed to unify enterprise and academic documentation, unstructured data, and multi-source workflows into an interactive, high-accuracy conversational exploration engine.

---

## 🌟 Key Features

- **Hybrid Retrieval-Augmented Generation (RAG):** Combines dense vector embeddings (pgvector) with sparse lexical search (BM25) and reciprocal rank fusion (RRF) for optimal context retrieval.
- **Local & Private LLM Inference:** Powered by Ollama / open-weights models (e.g., Llama 3 / Mistral) ensuring data privacy, low latency, and zero per-token cloud costs.
- **Agentic Workflows:** Autonomous reasoning agents capable of document routing, tool execution, multi-step problem solving, and structured reporting.
- **Interactive Modern Interface:** Reactive web dashboard built for low-latency queries, document visualization, and citation-backed answer exploration.
- **Production-Ready Observability:** Structured logging, metrics, latency tracking, and evaluation pipelines (RAGAS).

---

## 🏗️ System Architecture & Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React, TypeScript, Vite, Modern CSS |
| **Backend API** | Python, FastAPI, Uvicorn, Pydantic |
| **Vector DB & Storage** | PostgreSQL with `pgvector`, SQLAlchemy / asyncpg |
| **AI / Embeddings** | Ollama, HuggingFace Sentence Transformers, LangChain / LlamaIndex |
| **DevOps & Tooling** | Docker, Git, Ruff, Pytest |

---

## 📁 Repository Structure

```text
KNEXUS/
├── docs/                      # Project plan, design docs, specifications & research papers
├── Guidelines and NOtices/    # University/Major project guidelines and evaluation notices
├── Templates/                 # Report, presentation, and abstract templates
├── .gitignore                 # Version control exclusions
└── README.md                  # Project overview and setup documentation
```

*(Source code directories `frontend/`, `backend/`, and `infra/` will be organized in subsequent phases according to the project roadmap).*

---

## 🗺️ Roadmap & Phased Execution

Detailed project breakdown and division across phases:
- **Phase 1: Foundation & Ingestion Engine** — Environment setup, document parsers, database schema & pgvector setup.
- **Phase 2: Hybrid Search & RAG Core** — Dense/sparse embeddings, reranker pipeline, and FastAPI RAG endpoints.
- **Phase 3: Agentic Reasoning & Frontend UI** — Conversational frontend interface, agent tool-use, and session management.
- **Phase 4: Evaluation, Hardening & Final Submission** — RAGAS benchmark metrics, presentation slides, report compilation, and deployment packaging.

For the complete task division, refer to [`docs/KNEXUS_Project_Plan.md`](docs/KNEXUS_Project_Plan.md).

---

## 👥 Contributors

- **Major Project Team (2026–2027)**
