# Generation service

This package accepts canonical GenerationRequest evidence already authorized by the backend and returns GenerationResult. It selects no tenant/actor, reads no DB and executes no actions. The adapter is published in main; the non-streaming query route (`POST /api/v1/query`) calls it through the canonical `run_generation` boundary. The API owns all HTTP mapping (below); generation raises typed Python errors only.

## Implementation status (6 November 2026)

PR #13 merged the hosted chat-completions transport at main 1d4a06100b590a5f2a77830cbb3772eb789f0f47. It supports explicit openai/groq/mistral selection and retains canonical local validation. This is transport implementation, not evidence of live model/account/schema compatibility.

[PR #15](https://github.com/Hassan092-prog/KNEXUS/pull/15) remains open draft at e2658b627c8d92f35bd2d6e77b812175985e99d2, one commit ahead of main. Its four-file diff adds hosted_harness.py, test_hosted_harness.py, provider-aware live_harness.py provenance and README guidance. Development/held-out labels and explicit live/model/key gates are implemented in that branch; they do not authorize calls, enforce budgets or mechanically prevent held-out tuning.

Naveed's external integration-handoff-20261104.md rev 2 supersedes rev 1 and proposes further corrections. No such implementation or live execution was authorized by that handoff. The latest direction remains free-first with no paid expenditure, billing upgrade, automatic retries or fallback. Groq gpt-oss-120b is proposed, not account-verified; final hosted embeddings/model/dimension and privacy/quotas remain decisions. See [status](../../../../docs/PROJECT_STATUS.md) and [TRD](../../../../docs/TRD.md).

## Existing constructor and API wiring

GenerationService supports provider, url, model, timeout, num_ctx, num_predict, max_prompt_chars, seed, transport, api_key, api_base_url and temperature. Hosted model/key/base/temperature may resolve from GENERATION_MODEL, GENERATION_API_KEY, GENERATION_API_BASE_URL and GENERATION_TEMPERATURE; provider/timeout/output currently retain legacy OLLAMA_* environment names. Existing controls are code facts, not the agreed future Settings contract.

The hosted constructor resolves endpoint from api_base_url, its environment value or the provider default; url is used by legacy paths. Inspect this distinction rather than universally requiring url=None. Current API factory passes OLLAMA_PROVIDER, OLLAMA_MODEL, timeout and output settings and does not explicitly pass Settings-held hosted secrets. The legacy model can override hosted environment selection. Agree explicit validated Settings-to-constructor mapping before claiming the route is integrated.

Pydantic loading root .env does not export values into os.environ. A masked Settings secret passed explicitly is valid; whichever delivery is chosen, exclude credentials from logs, settings exports, errors and argv. Tests explicitly select/inject fake. Unconfigured application generation must fail clearly.

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

Default endpoint support in code: OpenAI https://api.openai.com/v1, Groq https://api.groq.com/openai/v1 and Mistral https://api.mistral.ai/v1. Endpoint support does not select a model, prove provider schema compatibility or authorize expenditure.

Current payload uses max_tokens from num_predict and a schema derived from GenerationResult with abstention_reason required/default-less. JSON is parsed and locally validated with citation membership. PR #15 does not implement the following proposed provider corrections:
- Provider-specific max_completion_tokens/output controls and explicit termination/refusal checks.
- A reviewed Groq schema compatibility projection if necessary. Undocumented keywords are not confirmed rejected; never recursively drop property names/structure. All canonical local invariants remain enforced.
- Usage/finish_reason/fingerprint capture before result parsing/validation can fail. A successful response with invalid output may still consume quota/cost.
- Optional reasoning_effort=low and include_reasoning=false. Hiding reasoning does not establish reduced computation, billing or completion-token consumption.
- Shared durable reserve-before-dispatch controls and verified generation input-token bounds.

These are bounded change proposals, not completed features. Preserve typed failures, network/overall deadlines, external cancellation and exact citations. Rate-limit diagnostics must be sanitized and bounded rather than copying provider content into public errors.

## Verification

Offline commands are in [CONTRIBUTING](../../../../CONTRIBUTING.md); recorded evidence is in [status](../../../../docs/PROJECT_STATUS.md). Use mocked HTTP for regressions. Regression-focused subsets: `backend/tests/test_h01_boundaries.py` and `backend/tests/phase1/generation/`.

## Historical local evaluation (llama3.2:3b, 2026-11-01; superseded deployment)

Bounded seeded runs (seed 42, 3 repeats each) are preserved outside the repository; raw artifacts and hashes are with the branch review. Headline outcomes, split by the layers above:

- Unsupported → abstention: expected behavior on all repeats (stable with a fixed seed).
- Conflict → abstention: model answered citing one authorized ID every repeat. Layers 1–3 all pass; **layer 4 fails stably** — llama3.2:3b does not abstain on conflicting evidence; nothing was structurally rejected.
- Injection case: layer 1–3 outcomes varied by prompt version; one stable mode produces an authorized-ID answer with renumbered inline markers, which layer 3 fail-closes as `MalformedOutputError`.
- Prompt-iteration record and dead ends are documented in the branch's PR description; only a small number of hypothesis-driven iterations were tried and the best-verified version (`v4`) kept.

These remain historical failures, not hosted acceptance results. The next decision is hosted provider/model selection; do not resume laptop-model tuning.

## Harness and live acceptance gate

Main still contains the historical Ollama live_harness.py. PR #15 adds hosted_harness.py with explicit --run-live, provider/model/key selection, fresh output-path protection and development/held-out groups. Do not recreate this work or run either harness as implied authorization.

Before live execution, agree token/quota policy, account access and privacy. Post-call usage cannot enforce an input-token ceiling. chars/3 is not a guaranteed bound for Unicode, message framing or schema overhead; local Harmony tokenization alone does not establish server representation. Strict input enforcement remains unresolved; use mocks until an approved solution or explicit revised policy exists.

A shared ledger must atomically reserve attempts/token/cost allowances under a cross-process lock before dispatch, durably survive crashes/restarts, and retain worst-case reservations for uncertain provider outcomes. Unknown usage is unknown, never zero. Capture available usage even when canonical validation fails. Keep one authoritative transactional state; audit records cannot independently determine allowance or be silently rewritten to imply success. No network/file/authorization side effects at import time.

Report every attempted case, timeout/error, abstention, expected citation set, semantic outcome and measured latency. Denominator is all attempts: all errors is failure. Freeze the development configuration before held-out reporting; labels do not enforce process discipline. N06 can run on an approved isolated checkout before merge, without shared DB access.

Historical local runs remain evidence about their own setup only. No live hosted run or paid spending is authorized by this documentation. See [evaluation](../../../../docs/EVALUATION_STRATEGY.md).
