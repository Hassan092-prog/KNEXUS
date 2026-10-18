# KNEXUS — Knowledge Network for EXploration and Unified Services

> **Implementation status - 18 October 2026:** This document describes the target design and acceptance criteria. Only the backend scaffold, dependency health route, and PostgreSQL/pgvector bootstrap are implemented. See [REPOSITORY_REVIEW.md](REPOSITORY_REVIEW.md) for current behavior and known gaps. Code examples, proposed directories, tests, and migrations below are not evidence of completed work.

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

# 🚀 Phased Implementation Plan

## Phase 0 — Pre-Development Foundation *(Weeks 1–2 | All Members)*
*Goal: Establish shared understanding, environment, and architecture before anyone writes production code.*

### All Members (Shared)
- [ ] Deep-read the base paper (Lewis et al. RAG 2020) and summarize key insights
- [ ] Read supporting papers (Research Papers 1 & 2 in the repo) and identify gaps
- [ ] Set up shared GitHub repository with branching strategy (feature branches, PRs)
- [ ] Set up development environments: Python, Node.js, PostgreSQL, Ollama
- [ ] Define the 8-slide Review-I PPT structure and divide slide ownership
- [ ] Write the 1-page abstract hardcopy (following MJCET template)
- [ ] Finalize system architecture diagram together

**Deliverable:** Shared architecture doc, GitHub repo, all environments working, Review-I PPT skeleton

---

## Phase 1 — Core RAG Pipeline + Data Infrastructure *(Weeks 3–6)*
*Goal: Build the foundational document ingestion, embedding, storage, and retrieval system. This is the beating heart of KNEXUS.*

### Member 1 — Project Lead & RAG Core Architect
**Technical Areas:** NLP/AI (embedding models), Backend (FastAPI), Database (pgvector), DevOps
- [ ] **Architecture & API design:** Define all FastAPI endpoint contracts (OpenAPI/Swagger spec) for the entire system before anyone builds
- [ ] **Document Ingestion Pipeline:** Build the document upload handler, text extraction module (PDFs, DOCX via `pdfplumber`/`python-docx`), and chunking logic (recursive character splitting, ~240 tokens with 32-token overlap)
- [ ] **Embedding Generation:** Integrate Sentence Transformers (e.g., `all-MiniLM-L6-v2` or `nomic-embed-text` via Ollama) and generate vector embeddings for each chunk
- [ ] **pgvector Setup:** Design the PostgreSQL schema (`documents`, `chunks`, `embeddings` tables), configure pgvector extension, and implement HNSW/IVFFlat index for fast ANN search
- [ ] **Semantic Search API:** Build the retrieval service behind `/api/v1/query` (a standalone `/search` route needs an agreed API contract); it — takes a query, embeds it, runs cosine similarity search in pgvector, returns top-K chunks with metadata
- [ ] **Abstention Logic:** Implement confidence thresholds — if similarity score is below threshold, system returns "Evidence not found" instead of hallucinating
- [ ] **Dataset Integration Script:** Write script to import 1,000–2,000 curated records from EnterpriseRAG-Bench (Linear + Slack + Gmail sources) into the KNEXUS corpus
- [ ] **RAG Evaluation Harness:** Build automated evaluation script that runs the 500-question test set and measures Retrieval Recall@K and Precision@K

**Technical Skills Gained:** Vector databases, embedding models, NLP preprocessing, FastAPI, PostgreSQL, evaluation metrics

---

### Member 2 — LLM Integration & Answer Generation Engineer
**Technical Areas:** Generative AI (Ollama/LLMs), Backend (FastAPI), Prompt Engineering, Testing
- [ ] **Ollama Setup & Model Selection:** Set up Ollama server locally, pull candidate models (Llama 3.2, Mistral 7B, Phi-3), benchmark latency and quality for enterprise Q&A
- [ ] **LLM Chain Architecture:** Build the generation pipeline — takes retrieved chunks + query → constructs prompt → calls Ollama → returns cited answer
- [ ] **Prompt Engineering:** Design and iterate on the system prompt that instructs the LLM to (a) answer only from provided context, (b) cite sources, (c) abstain if evidence is missing
- [ ] **Context Window Management:** Implement dynamic context assembly — rank and select chunks that fit within the model's context window (handle long-context cases gracefully)
- [ ] **Citation Formatting:** Build citation extractor that maps generated answer spans back to source document IDs and page/chunk references
- [ ] **Answer Quality Evaluator:** Implement automated evaluation for citation accuracy using the 500-question evaluation set (compare generated citations against ground truth)
- [ ] **Streaming Response Support:** Implement server-sent events (SSE) so the frontend receives streaming token output (better UX)
- [ ] **Unit Tests for RAG Chain:** Write comprehensive unit tests covering: retrieval quality, citation accuracy, abstention triggering, edge cases (empty context, very long queries)

**Technical Skills Gained:** LLM integration, prompt engineering, generative AI pipelines, API design, automated evaluation, testing

---

### Member 3 — Data Engineering & Infrastructure
**Technical Areas:** Data Engineering, Backend (FastAPI), DevOps/Docker, Database
- [ ] **Database Schema Design:** Collaboratively finalize then implement the full PostgreSQL schema including: `organizations`, `users`, `documents`, `document_chunks`, `embeddings`, `audit_logs`, `tool_proposals` tables (roles are a user field in this draft)
- [ ] **EnterpriseRAG-Bench Data Pipeline:** Download, inspect, and preprocess EnterpriseRAG-Bench from HuggingFace; write ETL pipeline to normalize records from Slack/Gmail/Linear/Google Drive formats into KNEXUS unified schema
- [ ] **Synthetic Security Dataset:** Create the KNEXUS custom synthetic test fixtures — define roles (admin, manager, employee), assign documents to roles, create test Q&A pairs where some queries should be blocked
- [ ] **Docker Compose Setup:** Create `docker-compose.yml` that orchestrates: PostgreSQL + pgvector, Ollama, FastAPI backend, React frontend — single command to start the full stack
- [ ] **Data Versioning & Migrations:** Set up Alembic for database migrations, ensuring schema evolution is tracked
- [ ] **Monitoring & Logging Infrastructure:** Set up structured logging (JSON logs), basic health check endpoints, and a simple dashboard to monitor ingestion progress
- [ ] **Performance Benchmarking:** Measure and document ingestion throughput, search latency (p50/p95), and generation latency end-to-end

**Technical Skills Gained:** Data engineering/ETL, Docker/DevOps, database design, infrastructure automation, performance testing

---

**Security sequencing:** Authentication, tenant ownership, and permission filtering must accompany initial ingestion/retrieval before any shared or sensitive corpus is used. Phase 2 expands governance and proves isolation; it must not be interpreted as permission to expose a cross-tenant query path first.

## Phase 2 — Security, Access Control & Governance *(Weeks 7–10)*
*Goal: Add RBAC, permission-aware retrieval, approval workflows, and audit logging — the features that differentiate KNEXUS from generic chatbots.*

### Member 1 — RBAC Architecture & Permission-Aware Retrieval
**Technical Areas:** Security/Auth, Backend, Database, AI Safety
- [ ] **Auth System:** Implement JWT-based authentication with FastAPI dependencies — `/login`, `/refresh`, `/logout` endpoints; secure password hashing (bcrypt)
- [ ] **RBAC Middleware:** Build role-based middleware that attaches user roles to every request; define role hierarchy (SuperAdmin > OrgAdmin > Manager > Employee)
- [ ] **Permission-Aware Retrieval Filter:** Extend the semantic search pipeline to pre-filter embeddings by `org_id` and `allowed_roles` BEFORE passing to the LLM — server-side enforcement (not frontend filtering)
- [ ] **Multi-Tenancy Isolation:** Implement organization-level data isolation — a user from Org A cannot retrieve documents from Org B even with the same role level
- [ ] **Access Control Testing:** Using the custom synthetic fixtures, write test suite validating: authorized access works, unauthorized access is denied, cross-tenant leakage is impossible
- [ ] **Security Review & Threat Modeling:** Write a brief security threat model for the system, identifying potential attack vectors (prompt injection, embedding poisoning, bypass attempts)

**Technical Skills Gained:** Security engineering, authentication systems, multi-tenancy architecture, threat modeling

---

### Member 2 — Controlled Tool Execution & Approval Workflows
**Technical Areas:** AI Agents/Tools, Backend (FastAPI), Workflow Design, Testing
- [ ] **Tool Registry:** Design and implement a controlled tool registry — define tools as typed Python functions with schemas (e.g., `create_task`, `update_document`, `send_notification`)
- [ ] **Approval Workflow Engine:** Build the human-in-the-loop approval system: (1) User proposes an action, (2) System logs the proposal with a hash of the payload, (3) Authorized approver reviews and approves/rejects, (4) System executes only if the payload hasn't changed
- [ ] **Post-Condition Verification:** After tool execution, implement a verification step that confirms the expected state change occurred (e.g., task was actually created)
- [ ] **Execution Audit Trail:** Log every tool invocation: proposed_by, proposed_at, approved_by, approved_at, executed_at, result, verification_status
- [ ] **Test Scenarios:** Implement the 6 key test scenarios from the dataset strategy: authorized valid task, unauthorized operation, expired approval, modified payload, successful creation, failed execution
- [ ] **Action Abstention:** If a proposed action requires a tool not in the registry or requires permissions the user doesn't have, return a structured "Cannot perform this action" response

**Technical Skills Gained:** Agent/tool systems, workflow orchestration, API design, state machines, audit systems

---

### Member 3 — Frontend Development & User Experience
**Technical Areas:** Frontend (React/TypeScript), UX Design, API Integration, Accessibility
- [ ] **Project Setup & Design System:** Initialize React + TypeScript app (Vite), set up component library structure, define color palette, typography, spacing tokens
- [ ] **Authentication UI:** Build Login page, role-aware navigation, session management, protected route guards
- [ ] **Knowledge Chat Interface:** Build the primary Q&A chat UI — conversation threads, streaming response display, citation cards that link to source documents, abstention messages
- [ ] **Document Management Panel:** Build the document upload UI (drag-and-drop), ingestion progress indicator, document library with metadata display, role-permission tags
- [ ] **Admin Dashboard:** Role management UI, user management, organization configuration, system health indicators
- [ ] **Approval Workflow UI:** Action proposal form, pending approvals queue for managers, approve/reject interface with diff view of proposed action
- [ ] **Responsive & Accessible Design:** Ensure the UI works on different screen sizes; follow WCAG 2.1 AA for accessibility

**Technical Skills Gained:** React/TypeScript, UX design, component architecture, API integration, accessibility

---

## Phase 3 — Integration, Evaluation & Optimization *(Weeks 11–14)*
*Goal: Connect all components, run comprehensive evaluation against the 500-question test set, and optimize for quality and performance.*

### Member 1 — System Integration & End-to-End Testing
**Technical Areas:** Integration Testing, CI/CD, System Architecture, Performance
- [ ] **End-to-End Integration:** Connect frontend → FastAPI → RAG pipeline → LLM → pgvector in a complete working flow; resolve all inter-component API contract mismatches
- [ ] **Integration Test Suite:** Write E2E tests covering complete user journeys: document upload → ingestion → search → cited answer → audit log entry
- [ ] **CI/CD Pipeline:** Set up GitHub Actions workflow — automated linting, unit tests, integration tests on every PR
- [ ] **Performance Optimization:** Profile retrieval latency, identify bottlenecks; tune pgvector index parameters (nlist, ef_construction); implement query result caching for repeated queries
- [ ] **Evaluation Report:** Run the 500-question EnterpriseRAG-Bench evaluation set, record Recall@K, Precision@K, answer quality (ROUGE/BERTScore), abstention accuracy; document results in a structured report
- [ ] **Load Testing:** Simulate concurrent users using Locust/k6 to assess system stability and identify breaking points

**Technical Skills Gained:** System integration, CI/CD, performance engineering, evaluation methodologies, load testing

---

### Member 2 — Model Tuning, Prompt Refinement & Knowledge Graph Extension
**Technical Areas:** NLP/AI, Prompt Engineering, Research, Documentation
- [ ] **Prompt A/B Testing:** Systematically test 3–5 prompt variants against the evaluation QA set; quantify which prompt template produces the most accurate, well-cited answers
- [ ] **Retrieval Strategy Experiments:** Compare retrieval strategies: vanilla cosine similarity vs. hybrid search (BM25 + dense retrieval) vs. re-ranking (cross-encoder); document gains
- [ ] **Hallucination Rate Analysis:** Categorize failure modes — cases where the system hallucinated vs. correctly abstained; analyze patterns
- [ ] **Research Paper Writing Support:** Draft the methodology, experiments, and results sections of the final project report; ensure all evaluation numbers are reproducible from the scripts
- [ ] **Demo Preparation:** Build a compelling live demo scenario using the EnterpriseRAG-Bench "Redwood Inference" fictional company — prepare 5-7 showcase queries demonstrating all key features (citation, abstention, RBAC, approval)

**Technical Skills Gained:** Experimental ML research, NLP evaluation, technical writing, demo engineering

---

### Member 3 — Final Report, Documentation & Deployment
**Technical Areas:** Technical Writing, Documentation, DevOps, Presentation
- [ ] **System Documentation:** Write complete API documentation (FastAPI auto-docs + Postman collection); document all KNEXUS configuration options
- [ ] **Final Report Compilation:** Compile the complete B.E. project report following MJCET guidelines — Introduction, Literature Survey, System Design, Implementation, Results, Conclusion, Future Work, References
- [ ] **User Manual:** Write an end-user guide explaining how to upload documents, ask questions, manage approvals, and interpret citations
- [ ] **Deployment Guide:** Document the complete local deployment process (Docker Compose); test it on a fresh machine
- [ ] **Review-II and Final PPT:** Design the Review-II and Final Defense presentations with system demo screenshots, architecture diagrams, results charts
- [ ] **Future Work Section:** Propose concrete future extensions — web connector (external retrieval), fine-tuned organization-specific embeddings, mobile app, enterprise SSO integration

**Technical Skills Gained:** Technical writing, documentation engineering, deployment, presentation design

---

## Phase 4 — Review Preparation & Defense *(Weeks 15–16)*
*Goal: Polish the deliverables, rehearse the presentation, and finalize all academic submissions.*

### All Members (Shared)
- [ ] Final run of the complete evaluation suite — document all numbers for the report
- [ ] Rehearse the live demo 3+ times with edge case handling prepared
- [ ] Print and collate hardcopy submissions: 1-page abstract + base paper + 2 supporting papers
- [ ] Peer-review each other's sections of the final report
- [ ] Prepare Q&A responses for likely panel questions (architecture decisions, model choices, dataset justification, RBAC design, scalability)
- [ ] Final code cleanup, README update, and repository archiving

---

# 👥 Team Member Summary

## Member 1 — Project Lead & System Architect

| Phase | Role | Technical Areas |
|---|---|---|
| Phase 0 | Co-architect, environment lead | System design, DevOps |
| Phase 1 | RAG Core + pgvector + Ingestion | NLP, Vector DB, FastAPI, Evaluation |
| Phase 2 | RBAC + Permission-Aware Retrieval | Security, Auth, Multi-tenancy |
| Phase 3 | E2E Integration + CI/CD + Evaluation | Integration, Performance, CI/CD |
| Phase 4 | Integration coordination, Q&A prep | All areas |

**Full-stack exposure:** AI/ML pipelines, Vector Databases, Security Engineering, System Integration, Performance Testing, CI/CD

---

## Member 2 — AI/LLM Engineer & Research Lead

| Phase | Role | Technical Areas |
|---|---|---|
| Phase 0 | Literature survey lead, research gaps | NLP, Research |
| Phase 1 | LLM Integration + Prompt Engineering + Testing | Generative AI, FastAPI, Evaluation |
| Phase 2 | Tool Execution + Approval Workflows | Agent Systems, Backend, Testing |
| Phase 3 | Model Tuning + Prompt Experiments + Demo | NLP Research, Prompt Engineering |
| Phase 4 | Demo rehearsal, report methodology | All areas |

**Full-stack exposure:** Generative AI/LLM, Prompt Engineering, Agent Systems, Automated Evaluation, Technical Writing, Demo Engineering

---

## Member 3 — Data & Infrastructure Engineer + Frontend Lead

| Phase | Role | Technical Areas |
|---|---|---|
| Phase 0 | Repo setup, Docker baseline | DevOps, Database |
| Phase 1 | Data ETL + DB Schema + Docker Compose | Data Engineering, PostgreSQL, DevOps |
| Phase 2 | Frontend (React/TypeScript) full build | Frontend, UX, API Integration |
| Phase 3 | Final Report + Documentation + Deployment | Technical Writing, Documentation |
| Phase 4 | PPT design, hardcopy compilation | Presentation, Documentation |

**Full-stack exposure:** Data Engineering, Docker/DevOps, Frontend (React/TypeScript), Database Design, Technical Writing, Documentation

---

# 🎓 Technical Skills Matrix

| Skill Area | Member 1 | Member 2 | Member 3 |
|---|---|---|---|
| RAG / NLP / Embeddings | ⭐⭐⭐ Primary | ⭐⭐ Secondary | ⭐ Exposed |
| LLM Integration / Prompt Engineering | ⭐⭐ Secondary | ⭐⭐⭐ Primary | ⭐ Exposed |
| FastAPI / Python Backend | ⭐⭐⭐ Primary | ⭐⭐ Secondary | ⭐⭐ Secondary |
| PostgreSQL / pgvector / Database | ⭐⭐⭐ Primary | ⭐ Exposed | ⭐⭐ Secondary |
| Security / Auth / RBAC | ⭐⭐⭐ Primary | ⭐⭐ Secondary | ⭐ Exposed |
| Agent Systems / Tool Execution | ⭐⭐ Secondary | ⭐⭐⭐ Primary | ⭐ Exposed |
| React / TypeScript / Frontend | ⭐ Exposed | ⭐ Exposed | ⭐⭐⭐ Primary |
| Data Engineering / ETL | ⭐⭐ Secondary | ⭐ Exposed | ⭐⭐⭐ Primary |
| Docker / DevOps / CI/CD | ⭐⭐ Secondary | ⭐ Exposed | ⭐⭐⭐ Primary |
| Evaluation / Testing | ⭐⭐⭐ Primary | ⭐⭐⭐ Primary | ⭐⭐ Secondary |
| Technical Writing / Report | ⭐⭐ Secondary | ⭐⭐ Secondary | ⭐⭐⭐ Primary |
| Research / Literature Survey | ⭐⭐ Secondary | ⭐⭐⭐ Primary | ⭐⭐ Secondary |

> [!TIP]
> Every member gets at least **Exposed (⭐)** to every technical domain, ensuring all three have breadth of experience for viva questions, industry interviews, and portfolio depth.

---

# 📊 Workload Distribution Overview

```
Phase 0 (Foundation):       M1 ████████ | M2 ████████ | M3 ████████  [Equal — 33% each]
Phase 1 (RAG + Data):       M1 █████████| M2 ████████ | M3 ████████  [M1 slightly more tasks]
Phase 2 (Security + UX):    M1 █████████| M2 ████████ | M3 ████████  [M1 leads security arch]
Phase 3 (Integration):      M1 █████████| M2 ████████ | M3 ████████  [M1 owns integration]
Phase 4 (Final):            M1 ████████ | M2 ████████ | M3 ████████  [Equal — 33% each]
```

---

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
> Review I PPT must contain these 8 sections. Divide slide ownership:

| Slide | Content | Owner |
|---|---|---|
| 1 | Title of Project | Member 3 (PPT design) |
| 2 | Problem Statement | Member 1 (led architecture) |
| 3 | Literature Survey (highlight base paper) | Member 2 (research lead) |
| 4 | Research Gaps | Member 2 (research lead) |
| 5 | Abstract | Member 1 |
| 6 | Existing Systems | Member 3 |
| 7 | Brief Overview of Proposed System | Member 1 |
| 8 | References | Member 2 |

**Hardcopy submissions on Review day:**
- [ ] 1-page abstract (MJCET template filled)
- [ ] Base paper printout (Lewis et al. RAG 2020)
- [ ] Research Paper 1 printout
- [ ] Research Paper 2 printout

---

*Last updated: October 2026 | KNEXUS Team 3 | MJCET CSE (AI&ML)*
