# PRD — Product Requirements Document
## KNEXUS: Knowledge Network for EXploration and Unified Services
**Version:** 1.0 | **Status:** Active | **Last Updated:** October 2026

---

## 1. Executive Summary

KNEXUS is an enterprise-grade AI knowledge platform that transforms how organizations access their internal knowledge. It ingests corporate documents, policies, SOPs, and technical manuals, and enables employees to ask natural language questions and receive accurate, source-cited answers — enforced by role-based access control and audited by an immutable trail.

The system runs entirely on-premise with locally-hosted LLMs (via Ollama), making it suitable for organizations with strict data privacy requirements.

---

## 2. Problem Statement

### 2.1 Core Pain Points

| Pain Point | Description | Current Workaround (Broken) |
|---|---|---|
| **Knowledge Scatter** | Company information lives across Google Drive, Notion, email, SOPs, manuals, Slack archives | Manual search, tribal knowledge |
| **Hallucination Risk** | Generic AI tools (ChatGPT, Copilot) fabricate information with false confidence | Fact-checking every AI response |
| **Access Control Gaps** | No AI tool enforces role-based document access at the retrieval level | Sharing only safe docs publicly |
| **Zero Auditability** | No audit trail of what was asked and what AI answered | Manual logging, unreliable |
| **Cloud Data Leakage** | Sending sensitive company docs to external AI APIs violates compliance | Blocking AI use entirely |

### 2.2 Target Users

| User Persona | Role | Primary Need |
|---|---|---|
| **Employee** | End user | Ask questions and get cited answers from authorized documents |
| **Manager** | Approver | Review and approve/reject AI-proposed actions before execution |
| **Org Admin** | Document owner | Upload, tag, and control access to organizational documents |
| **Super Admin** | Platform admin | Manage organizations, user roles, system health |

---

## 3. Goals & Non-Goals

### 3.1 Goals (MVP)

- ✅ Allow users to upload organizational documents (PDF, DOCX)
- ✅ Semantically index documents using vector embeddings
- ✅ Answer natural language queries with cited, evidence-backed responses
- ✅ Enforce server-side RBAC at the retrieval layer (not the UI)
- ✅ Support human-in-the-loop approval for sensitive AI-proposed actions
- ✅ Maintain an immutable audit log of all queries, answers, and actions
- ✅ Gracefully abstain when sufficient evidence is not available
- ✅ Run entirely locally with no mandatory cloud dependencies

### 3.2 Non-Goals (V1)

- ❌ Real-time web search / external knowledge connector
- ❌ Custom model fine-tuning or training
- ❌ Mobile application (Android/iOS)
- ❌ Enterprise SSO integration (SAML/OIDC)
- ❌ Multi-language document processing
- ❌ Voice interface

---

## 4. Feature Requirements

### 4.1 Document Ingestion

| ID | Requirement | Priority |
|---|---|---|
| F-ING-01 | System SHALL accept PDF and DOCX file uploads via API | P0 |
| F-ING-02 | System SHALL extract full text and metadata (title, author, date, source) | P0 |
| F-ING-03 | System SHALL chunk documents into ~512-token segments with 50-token overlap | P0 |
| F-ING-04 | System SHALL generate semantic vector embeddings for each chunk | P0 |
| F-ING-05 | System SHALL store embeddings in pgvector with associated metadata | P0 |
| F-ING-06 | System SHALL attach role-permission tags to each document at upload | P0 |
| F-ING-07 | System SHALL report ingestion progress status (queued / processing / complete / failed) | P1 |
| F-ING-08 | System SHALL support batch re-ingestion if embedding model changes | P2 |

### 4.2 Knowledge Retrieval (Semantic Search)

| ID | Requirement | Priority |
|---|---|---|
| F-RET-01 | System SHALL embed user query using the same model used for document chunking | P0 |
| F-RET-02 | System SHALL retrieve top-K relevant chunks via cosine similarity search (pgvector) | P0 |
| F-RET-03 | System SHALL pre-filter results by user role and organization BEFORE LLM call | P0 |
| F-RET-04 | System SHALL implement abstention: return "Evidence not found" if max similarity < threshold | P0 |
| F-RET-05 | System SHALL return source document ID and chunk metadata with every retrieved chunk | P0 |
| F-RET-06 | System SHOULD implement hybrid retrieval (BM25 + dense vector + RRF reranking) | P1 |

### 4.3 Answer Generation (LLM)

| ID | Requirement | Priority |
|---|---|---|
| F-GEN-01 | System SHALL use a locally-hosted LLM (Ollama) for answer generation | P0 |
| F-GEN-02 | System SHALL pass only retrieved chunks as context — no model parametric knowledge | P0 |
| F-GEN-03 | System SHALL include source citations mapped to specific chunks in every answer | P0 |
| F-GEN-04 | System SHALL support streaming token output via Server-Sent Events (SSE) | P1 |
| F-GEN-05 | System SHALL enforce abstention if context is empty or similarity is too low | P0 |
| F-GEN-06 | System SHALL support configurable system prompts per organization | P2 |

### 4.4 Access Control & Authentication

| ID | Requirement | Priority |
|---|---|---|
| F-AUTH-01 | System SHALL implement JWT-based authentication with refresh token support | P0 |
| F-AUTH-02 | System SHALL enforce role hierarchy: SuperAdmin > OrgAdmin > Manager > Employee | P0 |
| F-AUTH-03 | System SHALL isolate data between organizations (multi-tenancy) | P0 |
| F-AUTH-04 | System SHALL apply RBAC at the database query level (SQL filter), not UI | P0 |
| F-AUTH-05 | System SHALL block cross-tenant data access even for equal-level roles | P0 |

### 4.5 Human-in-the-Loop Approval Workflows

| ID | Requirement | Priority |
|---|---|---|
| F-APPR-01 | System SHALL maintain a registry of allowed AI-executable tools | P0 |
| F-APPR-02 | System SHALL submit action proposals for human approval before execution | P0 |
| F-APPR-03 | System SHALL hash action payloads and reject execution if payload was tampered | P0 |
| F-APPR-04 | System SHALL enforce approval expiry (proposals expire after configurable time) | P1 |
| F-APPR-05 | System SHALL verify post-execution state to confirm intended change occurred | P1 |
| F-APPR-06 | System SHALL notify the proposing user of approval/rejection | P2 |

### 4.6 Audit Logging

| ID | Requirement | Priority |
|---|---|---|
| F-AUD-01 | System SHALL log every query: user_id, query_text, retrieved_chunks, answer, timestamp | P0 |
| F-AUD-02 | System SHALL log every tool execution: proposed_by, approved_by, executed_at, result | P0 |
| F-AUD-03 | System SHALL log every document upload: uploader, doc_id, permissions applied | P0 |
| F-AUD-04 | Audit logs SHALL be append-only and not modifiable by any user role | P0 |
| F-AUD-05 | System SHOULD expose an admin-accessible audit log viewer with filters | P1 |

---

## 5. User Stories

### Employee
> *"As an employee, I want to ask a question about our expense policy and get a direct, cited answer so that I don't have to search through 50-page PDFs manually."*

> *"As an employee, I want the system to tell me when it doesn't know the answer instead of making something up."*

### Manager
> *"As a manager, I want to review AI-proposed actions before they are executed so that I remain accountable for automation decisions."*

### Org Admin
> *"As an org admin, I want to upload department SOPs and restrict access so that only relevant roles see sensitive financial documents."*

### Super Admin
> *"As a super admin, I want a complete audit trail of all AI-answered queries so that I can investigate any compliance incident."*

---

## 6. UX & Design Requirements

| Area | Requirement |
|---|---|
| **Response Time** | Search + generation end-to-end: < 8 seconds for first token (streaming) |
| **Interface** | React + TypeScript single-page application |
| **Citations** | Each answer must display clickable citation cards with source doc name and excerpt |
| **Abstention Message** | When abstaining, display a friendly, clear message — not a generic error |
| **Upload Feedback** | Document upload shows real-time ingestion progress |
| **Approval Queue** | Manager dashboard shows pending approvals clearly with diff view |
| **Accessibility** | Target WCAG 2.1 AA |

---

## 7. Performance & Quality Requirements

| Metric | Target |
|---|---|
| Query-to-first-token latency | ≤ 5 seconds (local LLM) |
| Retrieval precision@5 | ≥ 70% |
| Citation accuracy | ≥ 85% |
| Abstention accuracy | ≥ 90% (correct refusal when evidence absent) |
| Concurrent users supported | ≥ 20 (local deployment) |
| System availability | ≥ 99% (during active academic demo) |
| RBAC enforcement | 100% — zero cross-role leakage in test suite |

---

## 8. Constraints & Assumptions

- **No cloud LLM costs:** All inference runs locally via Ollama
- **Academic dataset:** Evaluation uses EnterpriseRAG-Bench + custom synthetic fixtures
- **Hardware:** Development and demo on the team's local machines (minimum 16GB RAM, GPU optional)
- **Time:** Project must reach demo-ready state by ~February 2027 (Review II)

---

*KNEXUS PRD v1.0 | MJCET CSE (AI&ML) | Team 3 | 2026–2027*
