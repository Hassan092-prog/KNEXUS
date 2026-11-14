# KNEXUS Project Status

**Date**: 14 November 2026
**Phase 1 Status**: Phase 1 demo-ready - final sign-off pending (Hassan).

## Merged into `main`
- **PR #15** (Naveed): Hosted generation evaluation harness and adapter corrections.
- **PR #21** (Hassan): Generation wiring, atomic QuotaLedger, UTC normalization, CI + CODEOWNERS, docs cleanup.
- **PR #23** (Zaid): Vite/React 19 dashboard in `frontend/app` (documents and assistant views, mock mode).
- **PR #26** (Hassan): CI Hugging Face tokenizer cache and pre-download step for offline tests.
- **PR #27** (Hassan): Demo runbook, status sync, and demo role setting.
- **PR #28** (Naveed): Offline hosted end-to-end demo path test (Google + Groq, mocked HTTP).
- **PR #29** (Hassan): Demo seed command (`python -m app.db.demo_seed`), port 8002, manager run.
- **PR #30** (Hassan): Server-approved live dispatch policy and controlled opt-in mechanism.
- **PR #31** (Hassan): Ingestion concurrency lock, rate-limit cooldown, and Groq pacing.
- **PR #33** (Naveed): Tolerant answer scoring (`expected_fact_any`) and similarity calibration for `run_demo.py`.
- **PR #25** (Zaid): Frontend Phase 1 delivery (live API integration, contracts, TanStack Query, error boundaries).
- **PR #35** (Zaid): Frontend assistant workspace and citation card UI polish.

## Continuous Integration (CI)
- **Backend CI**: Passing on `main` (all offline tests, persistence, and Phase 1 contract checks pass).
- **Frontend CI**: Passing on `main` (typecheck, lint, and contract tests pass).

## Model Policy
- All real AI usage goes through hosted APIs, called by the backend with server-held keys:
  - embeddings: Google gemini-embedding-001 at 384 dimensions via outputDimensionality, in backend/app/services/ingestion/embedding.py;
  - generation: Groq openai/gpt-oss-120b.
- The browser only calls the KNEXUS backend, never a provider, and holds no keys.
- Local models (MiniLM sentence-transformers/all-MiniLM-L6-v2) and the fake generator are for tests, CI and local development only. They are not the demo or production path.
- No automatic retries or fallback between providers. No paid usage without Hassan's approval.

## Live Verification Evidence
- **2026-11-07**: Local test mode (MiniLM + fake generator) verified live.
- **2026-11-14**: Full hosted provider rehearsal on server (`192.168.1.92`):
  - 12/12 demo question evaluation suite passed in live mode (Google `gemini-embedding-001` + Groq `openai/gpt-oss-120b`).
  - Browser UI verified live end-to-end (`http://192.168.1.92:5174`).
  - Ingested 45-page real text PDF in 11.5s using `TOKEN_COUNT_BYTE_BOUND_SKIP=true` (47 chunks).
  - Clean demo database `knexus_demo` created, seeded, and verified with all 5 demo documents in `complete` status.

## Remaining Steps to Phase 1 Complete
1. Hassan signs off Phase 1 after live rehearsal review.

## Branch Policy
- The only remote branches are `main`, `dev-hassan`, `dev-naveed`, and `dev-zaid`.
- Members open PRs from their own branch; only Hassan merges into `main` and teammate branches.
