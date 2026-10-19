# KNEXUS documentation index

**Reviewed: 19 October 2026.** Begin with the [repository review](REPOSITORY_REVIEW.md) for implementation status, findings, artifact coverage, and validation. The repository currently provides a backend scaffold; the specifications below describe the planned product.

## Setup and current behavior

| Document | Purpose |
|---|---|
| [README](../README.md) | Current capabilities, quick start, repository layout |
| [Contribution guide](../CONTRIBUTING.md) | POSIX/PowerShell setup, configuration, troubleshooting |
| [Repository review](REPOSITORY_REVIEW.md) | Code findings, missing implementation, academic conflicts, verification |
| [Team start](TEAM_START.md) | Published member branches, GitHub invitation status, contract PR handoff and laptop-hosted Ollama |
| [Frontend status](../frontend/README.md) | Proposed UI; no application initialized |
| [Data status](../data/README.md) | Proposed fixtures, corpus selection, provenance |

## Target design and delivery

| Document | Purpose |
|---|---|
| [PRD](PRD.md) | Product requirements and unmeasured acceptance targets |
| [TRD](TRD.md) | Technical baseline, configuration, engineering standards |
| [Architecture](ARCHITECTURE.md) | Current runtime summary and proposed components/tree |
| [API specification](API_SPEC.md) | Current routes followed by proposed contracts |
| [Phase 1 baseline](PHASE_1_CONTRACT.md) | Concrete draft fields, limits, data/service boundaries and deferred work |
| [Contract reference](../contracts/phase1/README.md) | Synthetic API/generation mocks, Pydantic reference types, JSON Schema and validator |
| [Database schema](DATABASE_SCHEMA.md) | Bootstrap scope and draft DDL/migration requirements |
| [Security model](SECURITY_MODEL.md) | Current gaps, planned policy, threat model, negative tests |
| [Evaluation strategy](EVALUATION_STRATEGY.md) | Dataset, metrics, proposed tests/CI; no measured results |
| [Team responsibilities](TEAM_RESPONSIBILITIES.md) | Member identities, branches and task ownership; Zaid owns the entire frontend |
| [Project plan](KNEXUS_Project_Plan.md) | Phases 0-4, delivery ownership and academic prerequisites |
| [Git workflow](KNEXUS_Team_Git_Workflow_Guide.md) | Persistent `dev-*` member branches, daily pushes, merge-commit PRs |
| [Phase 1 team guide](PHASE_1_TEAM_GUIDE.md) | Task ownership, integration gates, prompt and code-review templates, skills |

For current behavior, tracked source and generated OpenAPI take precedence. For the initial implementation slice, review PHASE_1_CONTRACT and its reference models; API_SPEC and DATABASE_SCHEMA describe broader targets with the qualifications in SECURITY_MODEL. The OpsPilot startup blueprint is background, not a competing implementation contract. For member identity, responsibilities and path ownership, TEAM_RESPONSIBILITIES.md takes precedence. Update related designs together when a decision changes.

## Academic and reference artifacts

| Artifact | Role and status |
|---|---|
| [University guidelines](../Guidelines%20and%20NOtices/Project%20Guidelines.pptx) | Source requirements: base-paper eligibility and literature survey |
| [Review-I notice](../Guidelines%20and%20NOtices/major%20project%20review%20notice.pdf) | Scanned notice dated 3 October 2026; eight presentation sections and required hardcopies |
| [Abstract template](../Templates/Major%20Project%20Abstract%20Template-2026-2027.doc) | Original blank university form |
| [Presentation template](../Templates/PROJECT%20PPT%20TEMPLATE.pptx) | Original slide template, intentionally contains placeholders |
| [Abstract DOC](Abstract/Major%20Project%20Abstract%202026-2027.doc) / [PDF](Abstract/Abstract.pdf) | Project proposal; administrative/student/guide fields still blank |
| [Team presentation](PPT/KNEXUS%20Team%203.pptx) | Ten-slide Review-I proposal; three-paper survey and parser choice need reconciliation |
| [Dataset report](KNEXUS_Dataset_Selection_and_Evaluation_Strategy.pdf) | Reference recommendation; historical counts, no measured KNEXUS results |
| [OpsPilot blueprint](OpsPilot_AI_Final_Startup_Blueprint.docx) | Broader eight-week/startup vision with different roles, routes, formats, and schema |
| [Base paper](Research%20Papers/Base_Paper.pdf) | Lewis et al., RAG, NeurIPS 2020; bundled arXiv revision April 2021 |
| [Supporting paper 1](Research%20Papers/research_paper_1.pdf) | Schick et al., Toolformer, 2023 |
| [Supporting paper 2](Research%20Papers/research_paper_2.pdf) | Zhao et al., AgentCDM, 2025 preprint |

Original PDFs, Office deliverables, papers, and university templates are preserved. See the review for corrections to carry into the next revision and the base-paper eligibility conflict.

## Suggested reading order

1. README and repository review: establish what runs today.
2. CONTRIBUTING: set up the scaffold.
3. PRD, architecture, API, and schema: understand the intended path.
4. Security and evaluation: understand boundaries and acceptance checks.
5. Project plan, workflow, and academic requirements: coordinate delivery.
