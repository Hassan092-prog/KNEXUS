# KNEXUS — Knowledge Network for EXploration and Unified Services

> **Implementation status - 19 October 2026:** This document describes the target design and acceptance criteria. Only the backend scaffold, dependency health route, and PostgreSQL/pgvector bootstrap are implemented. See [REPOSITORY_REVIEW.md](REPOSITORY_REVIEW.md) for current behavior and known gaps. Code examples, proposed directories, tests, and migrations below are not evidence of completed work.

## Comprehensive Team Project Plan | B.E. VII Semester | MJCET 2026–2027

---

> [!IMPORTANT]
> **Project Domain:** Artificial Intelligence & Machine Learning — Generative AI, Retrieval-Augmented Generation (RAG), Natural Language Processing, and Knowledge Management
>
> **Institution:** Muffakham Jah College of Engineering and Technology, CSE (AI&ML) Department
>
> **Review Requirements:** Review-I PPT must include: Title, Problem Statement, Literature Survey, Research Gaps, Abstract, Existing System, Proposed System Overview, References. Hardcopy of 1-page Abstract + Base Paper + 2 supporting papers required on Review day.

---

## 🔬 Project Overview

**KNEXUS** (*Knowledge Network for EXploration and Unified Services*) is an AI-powered company knowledge platform that solves a critical enterprise problem: organizations store critical information across scattered documents, policies, SOPs, and technical manuals, making it difficult for employees to access accurate information efficiently.

### Core Problem Being Solved
- Existing AI assistants generate unsupported ("hallucinated") answers
- Lack of adequate access control and accountability in AI systems
- Inefficient retrieval of accurate organizational knowledge

### Proposed Solution
KNEXUS is a RAG-based enterprise knowledge platform that:
1. **Ingests** organizational documents (PDFs, SOPs, manuals, policies)
2. **Retrieves** relevant document chunks using semantic search (embeddings + vector DB)
3. **Generates** context-aware, cited answers using a locally-hosted LLM
4. **Enforces** Role-Based Access Control (RBAC) — users only access authorized content
5. **Executes** controlled tasks with human-in-the-loop approval workflows
6. **Audits** all actions for transparency and accountability

### Technology Stack
| Layer | Technology |
|---|---|
| Frontend | React + TypeScript |
| Backend API | Python FastAPI |
| Vector Store | PostgreSQL + pgvector |
| LLM Inference | Ollama (local models) |
| Embeddings | Sentence Transformers or similar |
| Auth | JWT + RBAC middleware |
| Dataset | EnterpriseRAG-Bench (primary) + custom KNEXUS synthetic fixtures |

### Datasets
- **Primary:** EnterpriseRAG-Bench — simulated company data (Slack: 285,605 records, Gmail: 121,390, Linear: 35,308, Google Drive: 25,108 records)
- **Evaluation QA Set:** 500 questions across Basic (175), Semantic (125), Intra-document reasoning (40), Project-related (40), Constrained (30), Conflicting Info (20), Completeness (20), Miscellaneous (20), High-level (10), Information-not-found (20)
- **Security Test Set:** Custom synthetic fixtures for RBAC, tenant isolation, approval handling, tool execution

### Base Research Paper
**"Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks"** — Lewis et al. (Facebook AI Research, UCL, NYU), NeurIPS 2020 (bundled arXiv revision: April 2021)
- RAG combines a dense pre-trained retriever (BERT-based DPR) with a seq2seq generator (BART)
- End-to-end trained using MIPS (Maximum Inner Product Search) over a Wikipedia document index
- Key insight: parametric + non-parametric memory hybrid outperforms pure LM baselines on knowledge-intensive tasks

---

## 📋 Evaluation Criteria for KNEXUS System
| Metric | What It Tests |
|---|---|
| Retrieval Relevance | Does semantic search return the right document chunks? |
| Citation Accuracy | Are source citations correct and traceable? |
| Access Control | Does RBAC correctly filter restricted documents? |
| Abstention Behavior | Does the system refuse when evidence is insufficient? |
| Controlled Workflow | Are approval chains correctly enforced? |
| Audit Logging | Are all actions recorded accurately? |

---

## 🏗️ System Architecture Overview

```
[User / Admin Interface — React + TypeScript]
         ↕
[FastAPI Backend — Auth, RBAC, Routing]
         ↕                    ↕
[RAG Pipeline]         [Tool Execution Engine]
  ↓                          ↓
[Document Ingestion]   [Approval Workflow]
[Chunking + Embedding] [Tool Registry]
[pgvector Semantic Search] [Audit Logger]
  ↓
[Ollama LLM (local)]
  ↓
[Cited Answer Generation]
```

---

## Academic review prerequisites

The bundled university guidelines require a base paper published in a reputed journal on or after 2021 and a literature survey of at least ten papers from 2021 onward. The current base paper is NeurIPS 2020; its April 2021 arXiv revision does not establish qualifying publication. Obtain guide/coordinator acceptance or select a qualifying base paper; keep Lewis et al. as foundational background. Only three research PDFs are tracked, and the team deck surveys those three.

The abstract DOC/PDF still contains blank course, branch, team, student, and guide fields. Complete verified details and signatures before submission. Dates below are estimates, not confirmed notice dates. See the [repository review](REPOSITORY_REVIEW.md) for artifact findings.

## 📅 Project Timeline

| Review | Approximate Date | Deliverable |
|---|---|---|
| Review I | Late Oct – Early Nov 2026 | PPT: Title, Problem, Lit Survey, Research Gaps, Abstract, Existing System, Proposed System, References |
| Review II | ~Feb 2027 | Working prototype + progress report |
| Final Defense | ~May 2027 | Complete system + report + PPT |

---

# Phased implementation plan

The [team responsibilities](TEAM_RESPONSIBILITIES.md) define member identity, branch names and delivery ownership. Hassan is Member 1, Naveed is Member 2 and Zaid is Member 3. Zaid owns the entire frontend.

## Phase 0 - Pre-development foundation (Weeks 1-2)

Use [PHASE_0_SETUP_GUIDE.md](PHASE_0_SETUP_GUIDE.md) for ordered account/branch/tooling setup, observed readiness and the laptop inference connection. Its setup checklist supports the broader design/academic foundation tasks below.

| Owner | Responsibilities and exit evidence |
| --- | --- |
| Hassan (Member 1) | Define API/service/data contracts, own schema/runtime setup, organize integration; publish agreed contracts and reproducible backend setup |
| Naveed (Member 2) | Literature review, model/prompt baseline and quality rubric; document evidence and known limitations |
| Zaid (Member 3) | User flows, wireframes and frontend/API-state inventory; cover the eight required Review-I content sections in the visual plan |

All members review the base/supporting papers, attend design/rehearsal sessions and check the academic prerequisites. Original templates and papers are reference materials, not current task-allocation contracts.

## Phase 1 - Core RAG pipeline, storage and first frontend (Weeks 3-6)

Use [PHASE_1_TEAM_GUIDE.md](PHASE_1_TEAM_GUIDE.md) for branch commands, integration gates and collaborative prompts.

### Hassan (Member 1) - Backend, database, ingestion and retrieval

- [ ] Own FastAPI request/response contracts, routes and service orchestration.
- [ ] Implement tenant-consistent SQLAlchemy models, Alembic migrations, PostgreSQL/pgvector storage and vector indexes.
- [ ] Implement PDF/DOCX extraction, tokenizer-aware chunking (starting budget 240 tokens, 32 overlap) and 384-dimensional embedding generation.
- [ ] Implement top-k retrieval with tenant/role filters and low-evidence abstention before generation.
- [ ] Own dataset importer, source-ID/provenance manifests and synthetic security fixtures; use a coherent small corpus before expanding.
- [ ] Own root-based configuration, Compose/runtime setup, health/readiness follow-up, API errors and backend integration checks.

### Naveed (Member 2) - LLM generation and answer evaluation

- [ ] Implement the Ollama adapter with bounded provider failures and a fake provider for deterministic checks.
- [ ] Version the grounded-answer prompt and build bounded context from ranked, already-authorized chunks.
- [ ] Validate citations against retrieved source IDs, implement answer/abstention output handling, and label supported/missing/conflicting/adversarial answer cases.
- [ ] Record model/prompt versions and development/held-out split; contribute answer-quality labels to Hassan's evaluation harness.
- [ ] Stabilize a non-streaming answer path before adding SSE in a coordinated API change.

### Zaid (Member 3) - Frontend foundation, upload and chat

- [ ] Initialize the agreed React/TypeScript/Vite frontend and design tokens/component structure.
- [ ] Build upload/status views and the document list using typed mock payloads until Hassan's API is ready.
- [ ] Build chat, citation cards/source detail, abstention and loading/error/empty states.
- [ ] Own frontend API client/types, component checks, initial responsive behavior and accessibility.
- [ ] Connect to accepted API contracts after backend integration; document any mismatch in a coordinated PR.

**Security sequencing:** Authentication, tenant ownership and permission filtering accompany the first shared-data ingestion/retrieval path. Before authentication exists, keep the demo local with synthetic data and an explicitly fixed demo actor; do not expose it as an authenticated multi-tenant service. Frontend role controls do not authorize backend requests.

**Exit:** one reproducible upload -> parse/chunk/embed/store -> authorized retrieval -> cited answer or abstention -> frontend display path, with actual checks and known gaps recorded. A corpus subset does not justify claiming a full 500-question evaluation.

## Phase 2 - Security, controlled tools and frontend completion (Weeks 7-10)

### Hassan (Member 1) - Authorization, approval persistence and audit

- [ ] Implement JWT/session policy, role hierarchy, tenant ownership and retrieval authorization.
- [ ] Own approval state transitions, expiry recheck, exact-action binding, atomic single-use claims and idempotent execution orchestration.
- [ ] Implement audit persistence, tenant-safe administrative endpoints and execution verification records.
- [ ] Prove cross-tenant/role isolation and tamper/replay/concurrency behavior with backend integration checks.

### Naveed (Member 2) - Typed tools and AI regression cases

- [ ] Implement the server-owned typed tool registry and one low-risk local sandbox handler.
- [ ] Supply canonical action-envelope/integrity helpers and positive/negative tool cases for Hassan's approval engine.
- [ ] Evaluate prompt-injection, citation, abstention and tool-schema cases with fixed model/prompt versions.
- [ ] Keep model proposals separate from server authorization and approval decisions.

### Zaid (Member 3) - Login, approval and admin UI

- [ ] Implement login/session presentation, protected navigation and role-aware screen visibility.
- [ ] Build proposal detail, pending queue and approve/reject controls that show the exact reviewed payload.
- [ ] Build document/admin interfaces, permission state displays and user-facing failure handling.
- [ ] Keep frontend API types and component behavior aligned with generated backend contracts.

## Phase 3 - Integration, evaluation and final report (Weeks 11-14)

| Owner | Deliverables |
| --- | --- |
| Hassan (Member 1) | Full integration and CI, deployment/configuration, retrieval/load measurement and benchmark automation, final-report compilation, API/runtime documentation |
| Naveed (Member 2) | Controlled prompt/model/retrieval-quality experiments, research/methodology/results sections, answer-label review and demo narrative |
| Zaid (Member 3) | Frontend integration/usability/accessibility, UI verification, user manual/screenshots, report UI section and presentation visuals |

Hassan owns the evaluation harness and release/deployment process; Naveed owns answer-quality interpretation; Zaid owns frontend experience and UI evidence. Report measured numbers, dataset/source coverage, hardware and versions rather than copying target/sample metrics.

## Phase 4 - Review preparation and defense (Weeks 15-16)

| Owner | Deliverables |
| --- | --- |
| Hassan (Member 1) | Full-pipeline regression, release/archive, final report integration and defense coordination |
| Naveed (Member 2) | Verify research/results/limitations, rehearse model and workflow demo narrative |
| Zaid (Member 3) | Frontend polish, demo/PPT visuals, UI evidence and hardcopy/submission assembly |

All members rehearse and peer-review the final materials. Coordinate rehearsal slots and record remaining submission tasks.

# Team member summary

| Member | Branch | Primary ownership |
| --- | --- | --- |
| Hassan (1) | `dev-hassan` | Backend, schema/migrations, data/infra, ingestion/retrieval, authorization/approval/audit, CI/deployment, integration and report compilation |
| Naveed (2) | `dev-naveed` | LLM/prompt/context/citations, typed tool handlers, answer-quality experiments and research |
| Zaid (3) | `dev-zaid` | Entire frontend from Phase 1 through delivery, UI verification, user manual and presentation visuals |

# Technical skills and review exposure

| Area | Primary owner | Review/support |
|---|---|---|
| Backend/API, schema, vector storage, ETL, runtime/CI | Hassan | Naveed reviews AI interfaces; Zaid reviews client contracts |
| Tenant/role policy, approval transactions and audit | Hassan | Naveed reviews tool-integrity cases; Zaid reviews visible states |
| LLM adapters, prompts, citations, typed tool handlers | Naveed | Hassan reviews service/security boundaries |
| Frontend, UI API client, accessibility and usability | Zaid | Hassan reviews API integration; Naveed reviews evidence presentation |
| Evaluation harness/report compilation | Hassan | Naveed supplies answer/research analysis; Zaid supplies UI evidence |

Review exposure does not transfer accountable ownership.

# 📌 Key Decisions Summary

| Decision | Choice | Rationale |
|---|---|---|
| LLM | Ollama (local) | Cost-free, private, no API keys needed, aligns with project requirements |
| Embedding | Sentence Transformers / nomic-embed-text | High quality, runs locally via Ollama |
| Vector DB | PostgreSQL + pgvector | Unified database — no separate vector store to manage |
| Frontend | React + TypeScript | Industry standard, type-safe, rich ecosystem |
| Backend | Python FastAPI | Modern, async, auto-docs, Pythonic AI integration |
| Dataset | EnterpriseRAG-Bench + custom synthetic | Best fit for enterprise Q&A + security testing requirements |
| Security | JWT + server-side RBAC filter | Security boundary at server, not frontend |
| Corpus Size | 1,000–2,000 records initially | Manageable for development; easier to debug and evaluate |

---

# ⚡ Review I — Immediate Action Items

> [!IMPORTANT]
> Review I PPT must cover these eight content sections; the number of slides can differ. Section ownership follows the team responsibilities:

| Slide | Content | Owner |
|---|---|---|
| 1 | Title of Project | Zaid (Member 3; PPT design) |
| 2 | Problem Statement | Hassan (Member 1; architecture) |
| 3 | Literature Survey (highlight base paper) | Naveed (Member 2; research) |
| 4 | Research Gaps | Naveed (Member 2; research) |
| 5 | Abstract | Hassan (Member 1) |
| 6 | Existing Systems | Zaid (Member 3) |
| 7 | Brief Overview of Proposed System | Hassan (Member 1) |
| 8 | References | Naveed (Member 2) |

**Hardcopy submissions on Review day:**
- [ ] 1-page abstract (MJCET template filled)
- [ ] Base paper printout (Lewis et al. RAG 2020)
- [ ] Research Paper 1 printout
- [ ] Research Paper 2 printout

---

*Last updated: October 2026 | KNEXUS Team 3 | MJCET CSE (AI&ML)*
