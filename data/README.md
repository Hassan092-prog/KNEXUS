# KNEXUS data and fixtures

**Current state (19 October 2026):** this directory contains this README only. No datasets, fixtures, importer, benchmark file, or evaluation results are committed.

## Planned layout

- `samples/`: small normalized or synthetic enterprise-document examples.
- `evaluation/`: versioned QA manifests, gold source IDs, and expected abstentions.
- `fixtures/`: synthetic tenants, roles, document permissions, and approval cases.

Use the official [EnterpriseRAG-Bench repository](https://github.com/onyx-dot-app/EnterpriseRAG-Bench) and [dataset card](https://huggingface.co/datasets/onyx-dot-app/EnterpriseRAG-Bench). Its 500-question breakdown includes 20 Miscellaneous questions. Its Constrained category concerns qualifying evidence, not KNEXUS role permissions; add RBAC labels separately.

A 1,000-2,000-record development subset does not automatically support all 500 questions. Preserve supporting records and distractors, keep source IDs, and record which questions remain answerable. Report subset results separately from full-benchmark results.

Full datasets are **not currently excluded by a dedicated `.gitignore` rule**. Keep large downloads outside the repository, or add explicit ignore rules before placing them here. Commit only small, permitted, intentional fixtures. Record revision, provenance, license, selection rules, and development/held-out splits in future manifests.

See [EVALUATION_STRATEGY.md](../docs/EVALUATION_STRATEGY.md).
