# Documentation index

Read [project status](PROJECT_STATUS.md), [setup/workflow](../CONTRIBUTING.md), then your tasks in the [Phase 1 playbook](PHASE_1_TEAM_GUIDE.md).

## One source for each subject

| Document | Owns |
|---|---|
| [README](../README.md) | Introduction and source layout |
| [PROJECT_STATUS](PROJECT_STATUS.md) | Published checkpoint, evidence, next tasks and branch transition |
| [CONTRIBUTING](../CONTRIBUTING.md) | Setup, hosted transition, configuration and Git/PR workflow |
| [TEAM_RESPONSIBILITIES](TEAM_RESPONSIBILITIES.md) | Identity and ownership |
| [PHASE_1_TEAM_GUIDE](PHASE_1_TEAM_GUIDE.md) | H01-H07, N01-N06, Z01-Z06 and completion gates |
| [PHASE_1_CONTRACT](PHASE_1_CONTRACT.md) | Accepted Phase 1 semantics, limits and boundaries |
| [Contracts](../contracts/phase1/README.md) | Canonical models, schema, examples and checker |
| [API_SPEC](API_SPEC.md) | Implemented routes and future API scope |
| [DATABASE_SCHEMA](DATABASE_SCHEMA.md) | Tables, constraints, migration and seeding |
| [ARCHITECTURE](ARCHITECTURE.md) | Components and data flow |
| [TRD](TRD.md) | Approved hosted plan, pinned source-reuse policy and engineering standards |
| [PRD](PRD.md) | Product requirements |
| [SECURITY_MODEL](SECURITY_MODEL.md) | Current boundary, risks and later controls |
| [EVALUATION_STRATEGY](EVALUATION_STRATEGY.md) | Corpus, metrics and reproducibility |
| [Project plan](KNEXUS_Project_Plan.md) | Roadmap and academic requirements |
| [Backend tests](../backend/tests/README.md) | Test separation and disposable DB safeguards |
| [Generation](../backend/app/services/generation/README.md) | Configuration, injection, failures and live harness |
| [Frontend](../frontend/README.md) | Scaffold and client handoff |
| [Data](../data/README.md) | Corpus/fixture storage policy |

Committed code and generated OpenAPI define actual behavior. Canonical models, semantic validators and the reviewed Phase 1 contract define shared wire fields. JSON Schema alone does not express every invariant. Coordinate changes with consumers.

Phase 0, team-start and separate Git instructions are consolidated in CONTRIBUTING. Historical audit observations are superseded by status, security and academic notes; Git history retains those documents.

## Preserved academic and external references

| Artifact | Purpose / qualification |
|---|---|
| [University guidelines](../Guidelines%20and%20NOtices/Project%20Guidelines.pptx) | Institutional requirements |
| [Review-I notice](../Guidelines%20and%20NOtices/major%20project%20review%20notice.pdf) | Scanned notice, not a confirmed review date |
| [Abstract template](../Templates/Major%20Project%20Abstract%20Template-2026-2027.doc) | Original form |
| [Presentation template](../Templates/PROJECT%20PPT%20TEMPLATE.pptx) | Original slide template |
| [Abstract DOC](Abstract/Major%20Project%20Abstract%202026-2027.doc) / [PDF](Abstract/Abstract.pdf) | Proposal source/export; administrative details need completion |
| [Team presentation](PPT/KNEXUS%20Team%203.pptx) | Proposal; survey and parser choice need reconciliation |
| [Dataset report](KNEXUS_Dataset_Selection_and_Evaluation_Strategy.pdf) | Historical recommendation; Markdown evaluation strategy owns current policy |
| [OpsPilot blueprint](OpsPilot_AI_Final_Startup_Blueprint.docx) | Future-platform background; its APIs/roles are not KNEXUS contracts |
| [Base paper](Research%20Papers/Base_Paper.pdf) | Lewis et al., NeurIPS 2020; eligibility needs guide decision |
| [Supporting paper 1](Research%20Papers/research_paper_1.pdf) | Toolformer, 2023 |
| [Supporting paper 2](Research%20Papers/research_paper_2.pdf) | AgentCDM, 2025 preprint |

The [project plan](KNEXUS_Project_Plan.md) owns academic follow-up. Templates, source/export pairs and papers have distinct purposes. No byte-identical binary duplicates were found; originals are preserved rather than rewritten as current runtime instructions.
