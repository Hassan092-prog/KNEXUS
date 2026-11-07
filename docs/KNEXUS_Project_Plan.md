# Project roadmap and academic delivery

KNEXUS is an academic knowledge assistant with evidence-grounded answers and later governed sandbox actions. [Product requirements](PRD.md) own product scope, [ownership](TEAM_RESPONSIBILITIES.md) assigns roles, [status](PROJECT_STATUS.md) records progress and the [Phase 1 playbook](PHASE_1_TEAM_GUIDE.md) owns detailed tasks. This roadmap does not duplicate their checklists.

## Delivery phases

| Phase | Exit evidence |
|---|---|
| 0 - Foundation | Agreed schemas, environments, role boundaries and academic problem statement; setup is maintained in CONTRIBUTING |
| 1 - Core RAG and frontend | Synthetic PDF/DOCX -> persisted status -> chunks/hosted embeddings compatible with the reviewed schema -> permitted retrieval -> cited answer or abstention -> browser, with failure evidence |
| 2 - Identity and governed actions | Reviewed authentication/session behavior, tenant/role isolation, one allow-listed typed sandbox action, exact-payload approval, expiry/idempotency/concurrency controls and append-only audit |
| 3 - Evaluation and integration | Reproducible held-out retrieval/answer/security/UI results, measured runtime/load, dependency/CI decisions and integrated report |
| 4 - Submission | Rehearsed reproducible demo, verified results/limitations, completed report/abstract/slides and required hardcopies |

H01/H02 are implemented; Phase 1 as a whole is incomplete. A demo actor permits local synthetic development only. Authentication/authorization must precede shared-sensitive data or external deployment, even if the broader security milestone is Phase 2.

Hassan coordinates backend/data/runtime/integration; Naveed generation/tools/research; Zaid the full frontend and visuals. Accountable owners and paths live in the responsibility document.

## Scope after the core path

Hosted generation and embeddings, with selective reuse from the pinned personal project in [TRD](TRD.md), are now the Phase 1 target. Hosted generation transport (PR #13), offline hosted embedding dispatch protection (PR #16), and hosted input token validation (PR #19) are merged in main; draft PR #15 contains the generation evaluation harness. Final provider/model choices, API wiring, live token correspondence verification, and browser frontend remain pending. Connectors and broader business modules remain later reviewed decisions. Preserve adapter boundaries and a single PostgreSQL store, but do not add platform breadth, queues or agents simply to match a future blueprint. No commercial readiness is claimed by the academic prototype.

## Academic prerequisites

The bundled university guidelines require a base paper in a reputed journal on/after 2021 and at least ten quality papers from 2021 onward. The bundled Lewis et al. RAG paper is NeurIPS 2020; its April 2021 arXiv revision is not a qualifying publication date. Obtain guide/coordinator acceptance or choose a qualifying base paper while retaining RAG as background. Only three research PDFs are currently bundled.

The proposal abstract's administrative/student/guide fields and signatures need verified completion. The team deck surveys three papers and names PyMuPDF while backend dependencies currently select pdfplumber; reconcile the deck with the actual parser choice before submission.

The Review-I notice requires Title, Problem Statement, Literature Survey, Research Gaps, Abstract, Existing System, Proposed System and References, plus a one-page abstract, base paper and two supporting-paper hardcopies. Eight sections do not require exactly eight slides. Keep institutional originals intact.

Review-II around February 2027 and defense around May 2027 were planning estimates, not dates confirmed by the notice. Record actual dates only after confirmation.

## Academic ownership

| Material | Lead / contribution |
|---|---|
| Problem, abstract, architecture and integrated report | Hassan |
| Literature, research gaps, citations and measured model results | Naveed |
| Slide design, UI/manual/screenshots and submission visuals | Zaid |

All members understand and rehearse the entire project and check the final submission. Results must distinguish implemented behavior from proposals, measured evidence from illustrative examples and actual authorship from review assistance.

[Documentation index](INDEX.md) inventories preserved abstracts, templates, slides, dataset report, future-platform background and research papers. None of those replaces current runtime contracts.
