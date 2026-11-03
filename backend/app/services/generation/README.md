# Generation service

This package accepts canonical GenerationRequest evidence already authorized by the backend and returns GenerationResult. It selects no tenant/actor, reads no DB and executes no actions. The adapter is published in main; the non-streaming query route (`POST /api/v1/query`) calls it through the canonical `run_generation` boundary. The API owns all HTTP mapping (below); generation raises typed Python errors only.

## Approved target: hosted generation

The revised plan uses hosted APIs for generation and embeddings, not local models or model tunnels. Naveed selectively adapts relevant provider code from [enterprise-knowledge-bot at the pinned revision](https://github.com/Hassan092-prog/enterprise-knowledge-bot/tree/e67771a15f49a79443a365fbce85b8559ef43fb7), preserving licences, accurate authorship and KNEXUS's boundary. [TRD](../../../../docs/TRD.md) owns shared choices.

The hosted adapter, provider/model/endpoint and credential settings are pending. Do not assume an OpenAI-compatible protocol, invent environment names or present existing OLLAMA_* settings as hosted configuration. Use mocked HTTP until reviewed adapters and live-call authorization exist. No new SDK, billable call or model substitution is authorized by these instructions.

Preserve async generate(GenerationRequest) -> GenerationResult and app.core.generation.run_generation(service, request). Backend-authorized evidence only; no DB access, identity selection or tool execution. Keep explicit provider selection, finite positive network/overall deadlines, external cancellation, strict parsing and typed failures. Frontend clients call KNEXUS, never providers directly.

## Existing implementation (historical)

PR #12 merged prompt v4, constructor-only seed propagation and evaluation attribution. Current concrete providers remain fake and Ollama; hosted support is not implemented by this documentation change. OLLAMA_PROVIDER, OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT, OLLAMA_NUM_CTX, OLLAMA_NUM_PREDICT and GENERATION_MAX_PROMPT_CHARS describe that existing code, not the hosted target. seed and httpx transport are constructor-only.

The generator reads process environment, not root .env directly. Pydantic Settings does not export loaded values. Preserve this distinction when implementing explicit hosted configuration. Offline tests select fake deliberately; no silent fallback.

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

Default endpoints when `api_base_url` is not given: OpenAI `https://api.openai.com/v1`, Groq `https://api.groq.com/openai/v1`, Mistral `https://api.mistral.ai/v1`. **Team decision (2026-11-02): Groq at the default endpoint is the first hosted provider.** The concrete Groq model is not yet decided and stays pending Hassan's approval; the key is delivered by Hassan via server-side `GENERATION_API_KEY`, and no spending is authorized — live acceptance therefore remains pending. Proposed environment names (documented proposal pending Hassan's `Settings` wiring; constructor values always win): `GENERATION_API_KEY` (Bearer token; never appears in the request payload or logs), `GENERATION_API_BASE_URL`, `GENERATION_MODEL`, `GENERATION_TEMPERATURE` (default `0.0`). The `OLLAMA_*` environment names remain reserved for the ollama/fake paths; `OLLAMA_PROVIDER` stays the explicit provider selector for all providers.

Request details: `response_format` is a strict JSON schema derived from the canonical `GenerationResult` (`abstention_reason` becomes required and default-less to satisfy strict structured-output validation); `max_tokens` maps from `num_predict`; `seed` is included only when explicitly set; evidence and question are sent verbatim as the user message; the API key is sent only in the `Authorization: Bearer` header. Typed failures: invalid output/contract violations → `MalformedOutputError` (HTTP 502 via the published mapping), `httpx` errors/timeouts → `ProviderUnavailableError`/`ProviderTimeoutError` (503/504), missing key/unknown provider → `GenerationConfigurationError` before any call. Deliberate differences from the source: no LangChain dependency, no built-in retry/backoff (bounded retries deferred for review), no semantic cache or streaming. No billable API call may be made without explicit authorization; all verification so far is mocked HTTP (`backend/tests/phase1/generation/test_hosted_service.py`).

## Verification

Offline commands are in [CONTRIBUTING](../../../../CONTRIBUTING.md); recorded evidence is in [status](../../../../docs/PROJECT_STATUS.md). Use mocked HTTP for regressions. Regression-focused subsets: `backend/tests/test_h01_boundaries.py` and `backend/tests/phase1/generation/`.

## Historical local evaluation (llama3.2:3b, 2026-11-01; superseded deployment)

Bounded seeded runs (seed 42, 3 repeats each) are preserved outside the repository; raw artifacts and hashes are with the branch review. Headline outcomes, split by the layers above:

- Unsupported → abstention: expected behavior on all repeats (stable with a fixed seed).
- Conflict → abstention: model answered citing one authorized ID every repeat. Layers 1–3 all pass; **layer 4 fails stably** — llama3.2:3b does not abstain on conflicting evidence; nothing was structurally rejected.
- Injection case: layer 1–3 outcomes varied by prompt version; one stable mode produces an authorized-ID answer with renumbered inline markers, which layer 3 fail-closes as `MalformedOutputError`.
- Prompt-iteration record and dead ends are documented in the branch's PR description; only a small number of hypothesis-driven iterations were tried and the best-verified version (`v4`) kept.

These remain historical failures, not hosted acceptance results. The next decision is hosted provider/model selection; do not resume laptop-model tuning.

## Harness transition

The existing live_harness.py explicitly targets Ollama. Its --run-live flag is not a hosted API switch; do not execute it as hosted acceptance or start local inference to satisfy the revised plan.

Naveed must adapt reusable harness logic to an explicitly selected hosted adapter, with approved endpoint/model, secure credentials and bounded live-call/cost authorization. Preserve incremental JSONL, fresh output paths (the historical runner overwrites its target), exact citation-set expectations, prompt/configuration attribution, repeats, separate error/semantic outcomes, failing exit status, monotonic attempted-case timing and null latency for skipped inference.

Do not silently translate Ollama num_ctx/num_predict/seed semantics into another API or assume deterministic hosted output. Validate provider-specific token limits and structured-output capabilities. Mock rate limits, authentication, unavailable, timeout and invalid responses before approved live calls.

Historical local runs above remain evidence about their own configuration only; they do not establish hosted quality. See [evaluation](../../../../docs/EVALUATION_STRATEGY.md).
