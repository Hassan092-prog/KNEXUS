# Generation service

This package accepts canonical GenerationRequest evidence already authorized by the backend and returns GenerationResult. It selects no tenant/actor, reads no DB and executes no actions. The adapter is published in main; the non-streaming query route (`POST /api/v1/query`) calls it through the canonical `run_generation` boundary. The API owns all HTTP mapping (below); generation raises typed Python errors only.

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

Constructor arguments override process environment: `OLLAMA_PROVIDER`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT`, `OLLAMA_NUM_CTX`, `OLLAMA_NUM_PREDICT`, `GENERATION_MAX_PROMPT_CHARS`; the optional sampling `seed` and the httpx `transport` are constructor-only (no env names, no hidden defaults).

The generator reads `os.environ`, not root `.env` directly. Application Settings loads root `.env` but does not export it to the process or declare all generation controls. Pass explicit constructor values or export variables in the invoking shell; changing `.env` alone does not configure the standalone harness.

## Prompts and context budget

The prompt is versioned (`_GENERATION_PROMPT_VERSION`, currently `v4-hosted-1`: the shared v4 prompt text, suffixed to record that the chat-completions transport is in use). It is deterministic JSON: the question plus **every** supplied evidence item with citation IDs and source metadata, ended by the user-prompt marker reminder; the system prompt treats evidence as untrusted data and shows the exact required answer/abstention JSON shape. Nothing is filtered or reordered by heuristics: evidence containing phrases such as "user input:" is passed verbatim; conflict-vs-answer decisions belong to the model, not to service code.

Send the complete prompt or fail with `ContextBudgetExceededError` (before any provider call). The character ceiling is only a fail-closed size guard, not model token counting or proof of context fit. No compatible generation tokenizer has been selected. Explicit `num_ctx`/`num_predict` values do not resolve this limitation.

## Results: distinct validation layers

Do not conflate these five layers when reviewing outcomes:

1. **Provider execution** — did a call run, in bounded time?
2. **Structural validity** — result JSON satisfies the canonical GenerationResult schema (marker/cited-ID consistency, abstention invariants).
3. **Citation validity** — `validate_generation_result` membership in the authorized evidence.
4. **Expected answer/abstention behavior** — did the model do what the development case expects (e.g., abstain when relevant evidence conflicts)?
5. **Factual support** — does a cited passage actually support the claim?

Structural and citation validation are fail-closed: malformed JSON, invented IDs or marker mismatches raise `MalformedOutputError` and never leave the boundary. But a schema-valid answer that cites an authorized ID can still be **wrong behavior** (for example, answering from one source instead of abstaining under conflict) or **unsupported factually**; layers 4 and 5 are judged separately from evaluation records, not by the validator. A valid evidence-based abstention is a successful result. Provider failures never masquerade as abstentions; invalid answers are never repaired by dropping, renumbering or substituting citations.

## Failures and the published API mapping

Typed failures stay exceptions: `GenerationConfigurationError`, `ProviderTimeoutError`, `ProviderUnavailableError`, `MalformedOutputError` and `ContextBudgetExceededError`. Network and overall async deadlines are enforced; timeout must be finite and positive; external cancellation propagates.

`POST /api/v1/query` maps them as published: `ProviderTimeoutError` → 504/`PROVIDER_UNAVAILABLE`; `ProviderUnavailableError` → 503/`PROVIDER_UNAVAILABLE`; `GenerationConfigurationError` and `ContextBudgetExceededError` currently → 503/`PROVIDER_UNAVAILABLE`; `MalformedOutputError` → 502/`INVALID_CITATIONS`. Generation does not perform that mapping itself.

## Hosted providers (chat-completions adapter)

`hosted_provider.py` adds explicit hosted selection over OpenAI-compatible `/chat/completions` endpoints, adapted from Hassan's `enterprise-knowledge-bot` (source revision `e67771a15f49a79443a365fbce85b8559ef43fb7`; that repository ships no LICENSE file at this revision, and the adapted provider-selection concept is credited here rather than copied wholesale). The same canonical `GenerationRequest`/`GenerationResult` contract, v4 prompt text, evidence authorization, `run_generation` boundary and typed failures apply unchanged; only the transport and configuration differ.

~~~python
service = GenerationService(
    provider="openai",            # or "groq" / "mistral"
    model="<provider model name>",
    api_key="<secret>",           # or env GENERATION_API_KEY
    api_base_url="https://hosted.example/v1",  # optional override
    timeout=30, num_predict=512, seed=42, temperature=0.0,
)
~~~

Default endpoints when `api_base_url` is not given: OpenAI `https://api.openai.com/v1`, Groq `https://api.groq.com/openai/v1`, Mistral `https://api.mistral.ai/v1`. Proposed environment names (documented proposal pending Hassan's `Settings` wiring; constructor values always win): `GENERATION_API_KEY` (Bearer token; never appears in the request payload or logs), `GENERATION_API_BASE_URL`, `GENERATION_MODEL`, `GENERATION_TEMPERATURE` (default `0.0`). The `OLLAMA_*` environment names remain reserved for the ollama/fake paths; `OLLAMA_PROVIDER` stays the explicit provider selector for all providers.

Request details: `response_format` is a strict JSON schema derived from the canonical `GenerationResult` (`abstention_reason` becomes required and default-less to satisfy strict structured-output validation); `max_tokens` maps from `num_predict`; `seed` is included only when explicitly set; evidence and question are sent verbatim as the user message; the API key is sent only in the `Authorization: Bearer` header. Typed failures: invalid output/contract violations → `MalformedOutputError` (HTTP 502 via the published mapping), `httpx` errors/timeouts → `ProviderUnavailableError`/`ProviderTimeoutError` (503/504), missing key/unknown provider → `GenerationConfigurationError` before any call. Deliberate differences from the source: no LangChain dependency, no built-in retry/backoff (bounded retries deferred for review), no semantic cache or streaming. No billable API call may be made without explicit authorization; all verification so far is mocked HTTP (`backend/tests/phase1/generation/test_hosted_service.py`).

## Verification

Offline commands are in [CONTRIBUTING](../../../../CONTRIBUTING.md); recorded evidence is in [status](../../../../docs/PROJECT_STATUS.md). Use mocked HTTP for regressions. Regression-focused subsets: `backend/tests/test_h01_boundaries.py` and `backend/tests/phase1/generation/`.

## Recorded live evaluation (llama3.2:3b, Naveed's machine, 2026-11-01)

Bounded seeded runs (seed 42, 3 repeats each) are preserved outside the repository; raw artifacts and hashes are with the branch review. Headline outcomes, split by the layers above:

- Unsupported → abstention: expected behavior on all repeats (stable with a fixed seed).
- Conflict → abstention: model answered citing one authorized ID every repeat. Layers 1–3 all pass; **layer 4 fails stably** — llama3.2:3b does not abstain on conflicting evidence; nothing was structurally rejected.
- Injection case: layer 1–3 outcomes varied by prompt version; one stable mode produces an authorized-ID answer with renumbered inline markers, which layer 3 fail-closes as `MalformedOutputError`.
- Prompt-iteration record and dead ends are documented in the branch's PR description; only a small number of hypothesis-driven iterations were tried and the best-verified version (`v4`) kept.

Known limits remain open items; larger-model substitution is a separate decision for Hassan.

## Live harness

Live inference is opt-in and needs an approved running local Ollama/model. From the root, POSIX example:

~~~bash
OLLAMA_BASE_URL=http://127.0.0.1:11434 OLLAMA_TIMEOUT=30 backend/venv/bin/python backend/tests/phase1/generation/live_harness.py --run-live --model llama3.2:3b --timeout 40 --output /tmp/knexus-generation-run/results.jsonl
~~~

Choose a fresh output path: the harness opens its target in write mode. On Windows, export variables with PowerShell and use the existing Windows interpreter and a unique directory outside the repo.

Optional flags for reproducibility: `--repeat N` (complete bounded passes; each record carries `run_id`/`run_index`/`repeat_count`) and `--seed` (constructor-only sampling seed that reaches the Ollama `options`). Every record also carries `prompt_version`, `system_prompt_sha256`, `provider_url` and the effective Ollama options.

The live flag selects Ollama explicitly. The harness incrementally writes supported/unsupported/conflict/injection outcomes, requires exact expected citation sets, reports provider/harness deadlines as timeout and fails its exit status on failure/skip. Attempted cases use monotonic elapsed time; skipped cases have no measured inference. External cancellation propagates.

The harness does not judge all claims; factual support is reviewed separately from raw results. Baseline live quality limits above are known and preserved. See [evaluation](../../../../docs/EVALUATION_STRATEGY.md) and [tunnel setup](../../../../CONTRIBUTING.md).
