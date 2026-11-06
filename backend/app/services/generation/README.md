# Generation service

This package accepts canonical GenerationRequest evidence already authorized by the backend and returns GenerationResult. It selects no tenant/actor, reads no DB and executes no actions. The adapter is published in main; the non-streaming query route (`POST /api/v1/query`) calls it through the canonical `run_generation` boundary. The API owns all HTTP mapping (below); generation raises typed Python errors only.

## Implementation status (6 November 2026)

PR #13 merged the hosted chat-completions transport at main 1d4a06100b590a5f2a77830cbb3772eb789f0f47. It supports explicit openai/groq/mistral selection and retains canonical local validation. This is transport implementation, not evidence of live model/account/schema compatibility.

[PR #15](https://github.com/Hassan092-prog/KNEXUS/pull/15) remains an open draft; its branch carries the hosted harness work and now the committed composition of the shared dispatch/quota foundation into the hosted adapter. Development/held-out labels and explicit live/model/key gates are implemented on that branch; they do not authorize calls, enforce budgets or mechanically prevent held-out tuning.

Groq at its default endpoint remains the recorded first hosted provider, and Groq `openai/gpt-oss-120b` is the proposed candidate model. No other provider is assumed to share the Groq/OpenAI parameter surface; no new SDK, billable call or model substitution is authorized. Live dispatch stays blocked by default even when credentials, provider selection and harness flags exist; see the dispatch-policy section below.

Naveed's external integration-handoff-20261104.md rev 2 supersedes rev 1 and proposes further corrections. No such implementation or live execution was authorized by that handoff. The latest direction remains free-first with no paid expenditure, billing upgrade, automatic retries or fallback. Groq gpt-oss-120b is proposed, not account-verified; final hosted embeddings/model/dimension and privacy/quotas remain decisions. See [status](../../../../docs/PROJECT_STATUS.md) and [TRD](../../../../docs/TRD.md).

## Existing constructor and API wiring

GenerationService supports provider, url, model, timeout, num_ctx, num_predict, max_prompt_chars, seed, transport, api_key, api_base_url, temperature and, for hosted providers: dispatch_policy, quota_ledger, reasoning_effort and include_reasoning. Hosted model/key/base/temperature may resolve from GENERATION_MODEL, GENERATION_API_KEY, GENERATION_API_BASE_URL and GENERATION_TEMPERATURE; provider/timeout/output currently retain legacy OLLAMA_* environment names. Existing controls are code facts, not the agreed future Settings contract.

The hosted constructor resolves endpoint from api_base_url, its environment value or the provider default; url is used by legacy paths. Inspect this distinction rather than universally requiring url=None. Hosted providers without an explicitly injected dispatch_policy are fail-closed blocked, so the API factory must inject an approved DispatchPolicy and an explicit QuotaLedger before hosted generation can dispatch from the API route; that Settings-to-constructor wiring is Hassan-owned and its exact proposed patch is recorded in the PR description. Agree the final validated Settings-to-constructor mapping together before claiming the route is integrated.

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

Typed failures stay exceptions: `GenerationConfigurationError`, `ProviderTimeoutError`, `ProviderUnavailableError`, `MalformedOutputError`, `ContextBudgetExceededError` and `GenerationSettlementError` (settlement-failure wrapper mirroring the ingestion-side `TokenCountingSettlementError` pattern: the outstanding reservation is preserved and the preceding provider failure classification is kept in `provider_error`/`status_code`). Dispatch-policy and quota errors (`LiveInferenceBlockedError`, the `QuotaError` family) surface as published raw exceptions from `app.core.*`, not generation-service types. Network and overall async deadlines are enforced; timeout must be finite and positive; external cancellation propagates (ported through the ledger settlement path without conversion).

`POST /api/v1/query` maps them as published: `ProviderTimeoutError` → 504/`PROVIDER_UNAVAILABLE`; `ProviderUnavailableError` → 503/`PROVIDER_UNAVAILABLE`; `GenerationConfigurationError` and `ContextBudgetExceededError` currently → 503/`PROVIDER_UNAVAILABLE`; `MalformedOutputError` → 502/`INVALID_CITATIONS`. Generation does not perform that mapping itself. Not yet mapped (proposed 503 mapping patch pending Hassan's review in the PR description): `LiveInferenceBlockedError` and the `QuotaError` family, plus `GenerationSettlementError` (whose default fall-through currently ends at 500 on the API route). With the API factory not yet wiring an authorize-releasing policy, blocked dispatch from the route surfaces as an unmapped exception until that patch is applied.

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

Current payload sends `max_completion_tokens` from `num_predict` for the documented Groq/OpenAI parameter surface (Groq marks `max_tokens` deprecated; Mistral keeps documented-at-source `max_tokens` behavior) and a schema derived from GenerationResult with abstention_reason required/default-less; JSON is parsed and locally validated with citation membership. Hosted dispatch composes the published shared foundation:

- An explicit `DispatchPolicy` is checked before any HTTP client/socket creation; hosted providers default to `BlockedLiveDispatchPolicy` when none is injected. Keys, provider selection and harness flags never grant authorization.
- An explicit `QuotaLedger` (published `QuotaConfig`/`QuotaLedger` interface) reserves the attempt before dispatch and settles on every exit path. Available `usage` is captured before response parsing and canonical validation, so a successful provider response followed by invalid output still records actual tokens; missing usage stays unknown (the ledger records `tokens_unresolved`), never invented zero. Settlement failures propagate as a typed error while preserving the preceding provider failure classification, and outstanding reservations are never silently released.
- Termination and nonzero-output cases are deliberate: `finish_reason` truncation (`length`), refusal-only, reasoning-only and missing content map to explicit `MalformedOutputError` messages; valid abstention stays distinct from provider failure; HTTP 429 settles the ledger scope tripwire and raises without retry or fallback.
- The canonical schema keeps field names, structure, required/null semantics and all canonical constraints; a pinning test protects structure from recursive keyword filtering. Undocumented strict-mode keywords are neither assumed rejected nor silently removed.
- Optional `reasoning_effort` and `include_reasoning` remain explicit constructor parameters; hiding reasoning does not establish reduced computation, billing or completion-token consumption.

Honest accounting limits: the ledger provides request controls, not proven financial or strict token-budget enforcement. The `GENERATION_MAX_PROMPT_CHARS` ceiling above is a character guard, never a GPT-OSS token count. Rate-limit diagnostics stay sanitized and bounded rather than copying provider content into public errors. Composition note for Hassan's published ledger (documented, not fixed from this side): `reserve_attempt` does not enforce `in_flight_timeout_seconds`, so a stale active reservation blocks its scope until settled; settlement on uncertain outcomes settles the reservation rather than leaving it active indefinitely.

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

`hosted_harness.py` implements the hosted side, adapting the neutral runner. Selection and construction default to the recorded Groq decision; every record carries `case_group`, hosted provenance (provider, endpoint URL, model, `hosted_options`), prompt version/system-prompt hash, monotonic elapsed time for attempted cases and null latency for skipped ones, with separate error/semantic statuses and a failing exit code.

Fail-closed gating: no call is made without `--run-live`, a model (`--model` or `GENERATION_MODEL`), a non-empty server-side `GENERATION_API_KEY` and a fresh output path; the API key is never accepted as a CLI argument, never logged and never recorded. **CLI flags do not grant dispatch authorization**: with the default blocked policy the harness refuses before any call and names the remaining gate — an approved, explicitly injected `DispatchPolicy` together with an explicit `QuotaLedger` configuration is required in reviewed code before a live run can be scheduled. Keys, provider selection and harness flags never satisfy that gate. `--cases` selects `development` (the four v4 cases), `held-out` (four distinct synthetic facts, recorded for reporting only — never tuned against) or `all`. Response shapes, gating and authorization refusals are pinned by `test_hosted_harness.py` using mocked HTTP only. Provider-specific token limits and determinism remain unvalidated until an authorized live run; the character-ceiling limitation above is unchanged.

Report every attempted case, timeout/error, abstention, expected citation set, semantic outcome and measured latency. Denominator is all attempts: all errors is failure. Freeze the development configuration before held-out reporting; labels do not enforce process discipline. N06 can run on an approved isolated checkout before merge, without shared DB access.

Historical local runs remain evidence about their own setup only; they do not establish hosted quality. No live hosted run or paid spending is authorized by this documentation. See [evaluation](../../../../docs/EVALUATION_STRATEGY.md).
