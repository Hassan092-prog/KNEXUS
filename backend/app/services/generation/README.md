# Generation service

The generation package implements the Phase 1 asynchronous boundary. The backend passes a `GenerationRequest` containing already-authorized evidence and receives a canonical `GenerationResult`. It does not select a user or organization, access the database, or execute actions.

## Provider configuration

Provider selection is explicit:

```dotenv
OLLAMA_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.2:3b
OLLAMA_TIMEOUT=30
OLLAMA_NUM_CTX=8192
OLLAMA_NUM_PREDICT=512
GENERATION_MAX_PROMPT_CHARS=12000
```

Offline tests select `provider="fake"` explicitly. The fake is a shape and boundary test double; it does not demonstrate factual answer quality. Unknown or missing providers raise configuration errors.

The Ollama adapter sends the question and every evidence item as structured JSON, requests the canonical result schema, and validates inline citation markers and cited-ID membership. A valid abstention is a successful result. Provider timeouts, unavailable service, malformed output, and invalid citations remain typed failures.

## Context limit

The service sends the complete question and evidence or fails with `ContextBudgetExceededError`. It never silently cuts off evidence. The configured character ceiling is only a fail-closed size guard; it does not count model tokens or prove the real context-window fit. No compatible tokenizer has been selected for generation context. Ollama receives explicit `num_ctx` and `num_predict` limits; context fit remains an integration limitation to measure.

## Offline checks

From the repository root using the existing backend environment:

```bash
backend/venv/bin/python -m pytest backend/tests/test_h01_boundaries.py backend/tests/phase1/generation -q
backend/venv/bin/python contracts/phase1/check.py
```

The live harness is opt-in and does not run during import or unit tests:

```bash
OLLAMA_PROVIDER=ollama backend/venv/bin/python backend/tests/phase1/generation/live_harness.py --run-live
```

It writes each synthetic case result to JSONL as it completes. It checks expected abstention and citation IDs, not whether every answer claim is factually supported by a cited passage. Live results have not been produced by this baseline.
