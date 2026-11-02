# Generation service

This package accepts canonical GenerationRequest evidence already authorized by the backend and returns GenerationResult. It selects no tenant/actor, reads no DB and executes no actions. The adapter is published in main; Hassan's local H03-H06 draft calls it from the non-streaming query route, but that route is not yet published.

## Construction and H01 injection

~~~python
from app.core.generation import run_generation
from app.services.generation.generator import GenerationService

service = GenerationService(
    provider="ollama",
    url="http://127.0.0.1:11434",
    model="llama3.2:3b",
    timeout=30,
    num_ctx=8192,
    num_predict=512,
    max_prompt_chars=12000,
)
# Inside an async caller with a canonical request:
# result = await run_generation(service, request)
~~~

Offline checks explicitly select `provider="fake"`. It proves shape/boundary behavior only. Missing or unknown providers fail configuration.

Constructor arguments override process environment: `OLLAMA_PROVIDER`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT`, `OLLAMA_NUM_CTX`, `OLLAMA_NUM_PREDICT` and `GENERATION_MAX_PROMPT_CHARS`.

The generator reads `os.environ`, not root `.env` directly. Application Settings loads root `.env` but does not export it to the process or declare all generation controls. Pass explicit constructor values or export variables in the invoking shell; changing `.env` alone does not configure the standalone harness.

## Results and failures

The prompt contains the question and every evidence item as structured JSON. Ollama receives the canonical structured-result schema and explicit context/output limits. Validation checks result shape, inline markers and evidence membership, not factual claim support.

A valid evidence-based abstention is successful. [Typed failures](errors.py) remain exceptions: `GenerationConfigurationError`, `ProviderTimeoutError`, `ProviderUnavailableError`, `MalformedOutputError` and `ContextBudgetExceededError`. Network and overall async deadlines are enforced; timeout must be finite and positive; external cancellation propagates. Hassan maps service failures to the agreed [HTTP contract](../../../../docs/PHASE_1_CONTRACT.md).

## Context limitation

Send the complete prompt or fail with `ContextBudgetExceededError`. No fixture-specific filtering, caller mutation or silent truncation is permitted. The character ceiling is only a size guard, not model token counting or proof of context fit. No compatible generation tokenizer has been selected. Explicit `num_ctx`/`num_predict` values do not resolve this limitation.

## Verification

Offline commands are in [CONTRIBUTING](../../../../CONTRIBUTING.md); recorded evidence is in [status](../../../../docs/PROJECT_STATUS.md). Use mocked HTTP for regressions.

Live inference is opt-in and needs an approved running local Ollama/model. From the root, POSIX example:

~~~bash
OLLAMA_BASE_URL=http://127.0.0.1:11434 OLLAMA_TIMEOUT=30 backend/venv/bin/python backend/tests/phase1/generation/live_harness.py --run-live --model llama3.2:3b --timeout 40 --output /tmp/knexus-generation-run/results.jsonl
~~~

Choose a fresh output path: the harness opens its target in write mode. On Windows, export variables with PowerShell and use the existing Windows interpreter and a unique directory outside the repo.

The live flag selects Ollama explicitly. The harness incrementally writes supported/unsupported/conflict/injection outcomes, requires exact expected citation sets, reports provider/harness deadlines as timeout and fails its exit status on failure/skip. Attempted cases use monotonic elapsed time; skipped cases have no measured inference. External cancellation propagates.

The harness does not judge all claims or automatically capture full model/hardware/source provenance. Naveed must record these beside raw results and preserve failed runs. Baseline live quality remains unverified. See [evaluation](../../../../docs/EVALUATION_STRATEGY.md) and [tunnel setup](../../../../CONTRIBUTING.md).
