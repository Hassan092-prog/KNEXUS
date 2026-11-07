# KNEXUS Project Status

**Date**: 7 November 2026
**Phase 1 Status**: In progress (not complete).

## Merged into `main`
- **PR #15** (Naveed): Hosted generation evaluation harness and adapter corrections.
- **PR #21** (Hassan): Generation wiring, atomic QuotaLedger, UTC normalization, CI + CODEOWNERS, docs cleanup.
- **PR #23** (Zaid): Vite/React 19 dashboard in `frontend/app` (documents and assistant views, mock mode).
- **PR #26** (Hassan): CI Hugging Face tokenizer cache and pre-download step for offline tests.

## Continuous Integration (CI)
- **Backend CI**: Passing on `main` (all offline tests and Phase 1 contract checks pass).
- **Frontend CI**: Failing on `main` until Zaid's PR #25 fixes typecheck and test setup (`setup.ts:16`).

## Open Pull Requests
- **PR #24** (`dev-naveed` -> `main`): 5 Acme demo DOCX files + 12 questions + demo runner (in progress).
- **PR #25** (`dev-zaid` -> `main`): Frontend fixes (typecheck and test resolution; live backend wiring to do).

## Model Policy
- All real AI usage goes through hosted APIs, called by the backend with server-held keys:
  - embeddings: Google gemini-embedding-001 at 384 dimensions via outputDimensionality, in backend/app/services/ingestion/embedding.py;
  - generation: Groq openai/gpt-oss-120b.
- The browser only calls the KNEXUS backend, never a provider, and holds no keys.
- Local models (MiniLM sentence-transformers/all-MiniLM-L6-v2) and the fake generator are for tests, CI and local development only. They are not the demo or production path.
- No automatic retries or fallback between providers. No paid usage without Hassan's approval.

## Dry-Run Verification Evidence
- **2026-11-07**: Local test mode (MiniLM + fake generator) verified live: health 200, DOCX upload 202, ingestion complete (3/3 chunks, 100%), document listed, query answered with real document citations [1].

## Remaining Steps to Phase 1 Demo
1. Merge PR #24 and PR #25 with green CI.
2. Frontend live mode against the backend.
3. An offline end-to-end test of the hosted path through the API (upload -> Google embeddings -> retrieval -> Groq answer) using mocked HTTP only.
4. The live demo with Google embeddings + Groq. It needs Hassan to set GOOGLE/GENERATION API keys on the server and a QUOTA_CAMPAIGN_ID.
5. Hassan signs off Phase 1.

## Branch Policy
- The only remote branches are `main`, `dev-hassan`, `dev-naveed`, and `dev-zaid`.
- Members open PRs from their own branch; only Hassan merges into `main` and teammate branches.
