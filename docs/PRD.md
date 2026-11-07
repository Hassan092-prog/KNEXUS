# Product requirements

KNEXUS aims to answer organizational questions from permitted evidence with traceable citations, then support one explicitly approved sandbox action. This is an academic prototype, not a production security or availability claim. [Project status](PROJECT_STATUS.md) distinguishes implemented modules from these requirements.

## Users and scope

Employees ask questions over accessible documents; managers later review action proposals; organization admins manage documents/users; superadmins administer explicitly authorized platform operations. Role vocabulary and tenant boundaries follow the [canonical Phase 1 contract](PHASE_1_CONTRACT.md) and [security model](SECURITY_MODEL.md).

Phase 1 delivers a local synthetic PDF/DOCX upload-to-answer flow with a server-owned demo actor. It is not authenticated multi-tenant deployment. Phase 2 adds real identity, governance and audit before sensitive/shared data is accepted.

For the Phase 1 demo, the architecture uses local MiniLM embeddings (sentence-transformers/all-MiniLM-L6-v2, 384 dimensions) paired with Groq hosted generation (openai/gpt-oss-120b). The Google hosted embedder is implemented and verified offline in the codebase but kept disabled (EMBEDDING_PROVIDER="local") for the demo to preserve existing 384-d vectors and zero-cost operation. PR #13 merged hosted transport; PR #15 supplies the generation harness; PR #16 merged offline dispatch protection and quota ledger; PR #19 merged hosted input validation; PR #21 wires generation into backend dependencies. No local LLM hosting, downloads or model reverse tunnels are required.

## Functional requirements

Existing identifiers remain stable for future issue/test traceability. Priority indicates product importance, not proof that a feature belongs to the current slice.

| IDs | Required outcome |
|---|---|
| F-ING-01..02 | PDF/DOCX validation, text extraction and available source metadata |
| F-ING-03..05 | Tokenizer-aware chunks, consistent embedding model/dimension and pgvector persistence |
| F-ING-06..08 | Document permissions, real processing status and an explicit re-ingestion policy |
| F-RET-01..05 | Same query/document embedder, ranked cosine retrieval, pre-generation tenant/role filtering, low-evidence abstention and source IDs |
| F-RET-06 | Optional later hybrid retrieval/reranking after the dense baseline is measured |
| F-GEN-01..03 | Configured hosted provider, evidence-only answer policy and validated citations |
| F-GEN-04 | Streaming deferred until a separate reviewed wire contract |
| F-GEN-05..06 | Abstention on insufficient evidence; optional later organization-specific prompts |
| F-AUTH-01..05 | Reviewed authentication/session policy, role hierarchy, tenant isolation and server-side query authorization |
| F-APPR-01..05 | Allow-listed typed tools, human approval, exact action binding, expiry and postcondition verification |
| F-APPR-06 | Optional later user notification after approval/rejection |
| F-AUD-01..05 | Safe upload/query/action events, append-only runtime access and an authorized audit viewer |

The Phase 1 contract owns exact file limits, request/response fields and errors. The database foundation alone does not satisfy ingestion, retrieval or authentication requirements.

## User experience and acceptance

The interface must clearly separate loading, processing, failed, answered and abstained states; expose returned citations; support keyboard use and readable error announcements; and never hide a live failure behind mock success.

Acceptance requires a reproducible browser flow, source-grounded answers and negative authorization/error cases. Quantitative quality, latency and load targets are maintained only in [evaluation strategy](EVALUATION_STRATEGY.md); they are unmeasured goals, not product claims.

## Excluded from the initial delivery

No unrestricted web retrieval, model training, CSV agents, Graph RAG, arbitrary generated SQL/commands, external business connectors, SSO, mobile/voice application or commercial platform breadth is required for Phase 1. Login/admin/approval screens and governed actions are later work. Keep the core path complete before expanding modules.

The [project plan](KNEXUS_Project_Plan.md) owns phase sequencing and academic requirements; [team responsibilities](TEAM_RESPONSIBILITIES.md) owns delivery roles.
