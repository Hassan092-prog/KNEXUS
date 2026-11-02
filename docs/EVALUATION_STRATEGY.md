# Evaluation and reproducibility

[Project status](PROJECT_STATUS.md) owns actual pass counts and limitations. [Backend testing](../backend/tests/README.md) owns database safeguards; [generation guidance](../backend/app/services/generation/README.md) owns harness invocation.

Offline boundary/generation/persistence coverage and a disposable database run exist. A full retrieval benchmark, frontend suite, load harness and CI workflow do not. Do not copy illustrative metrics or test pseudocode into a results report.

## Data selection

Begin with a small labeled synthetic PDF/DOCX corpus for the complete pipeline. EnterpriseRAG-Bench remains the proposed broader corpus: [upstream repository](https://github.com/onyx-dot-app/EnterpriseRAG-Bench) and [dataset card](https://huggingface.co/datasets/onyx-dot-app/EnterpriseRAG-Bench).

Pin and record the imported revision, license, exact record inventory and selection rules before formal scoring. Historical record counts in the bundled dataset PDF are not a current inventory.

The historical 500-question category breakdown is Basic 175, Semantic 125, Intra-document 40, Project-related 40, Constrained 30, Conflicting 20, Completeness 20, Miscellaneous 20, High-level 10 and Information-not-found 20. Verify it against the selected revision before a formal report. Constrained questions disambiguate evidence; they do not provide KNEXUS role labels.

A possible 1,000-2,000-record development subset does not make all 500 questions answerable. Preserve answer sources and distractors, source IDs and question coverage. Report subset and full-corpus results separately. Add synthetic tenants/roles, revoked permissions and action cases independently.

## Scoring policy

Define the label unit and denominator before evaluation:
- Retrieval precision/recall at K: distinguish document and chunk labels, deduplicate for document-level scoring and state the convention when fewer than K results return.
- MRR: reciprocal rank of the first relevant labeled result, averaged over the declared eligible question set.
- Citation validity: structural membership and inline-marker consistency.
- Citation accuracy/claim support: whether the cited passage actually supports the claim, assessed separately from ID validity.
- Faithfulness/hallucination: claim-level support with a declared rubric and human review; lexical overlap is only a proxy.
- Abstention: report correct abstentions on unsupported questions AND false abstentions on answerable questions.
- Authorization: zero leakage in the declared tenant/role/revocation/status/deletion scenarios; passing a finite suite is not a universal guarantee.

Use separate development/tuning and held-out questions. Do not tune prompt, threshold or model after viewing held-out answers and still label them held out. Skip retrieval recall/MRR where no gold sources exist and report exclusions/denominators explicitly.

## Initial targets, not measurements

These targets require recalibration on documented hardware/load; no score is claimed.

| Measure | Proposed target |
|---|---|
| Precision@5 / recall@5 | At least 0.70, with scoring units declared |
| MRR | At least 0.75 |
| Citation accuracy | At least 0.85 |
| Faithfulness | At least 0.80 |
| Correct abstention on unsupported questions | At least 0.90; also report false abstentions |
| Answers with unsupported claims | At most 0.10 |
| End-to-end benchmark correctness | At least 0.70 on the declared eligible set |
| Retrieval latency | p50 below 100 ms / p95 below 300 ms |
| Full-response latency | p95 at most 12 seconds on declared hardware/load |
| Later streaming first-token latency | p50 at most 5 s / p95 at most 8 s; not a Phase 1 non-streaming metric |
| Document processing, 10-page PDF | p50 below 3 s / p95 below 8 s, subject to hardware recalibration |
| Later login latency | p50 below 200 ms / p95 below 500 ms |
| Load goal | 20 concurrent users, measured only after a working baseline |
| Service-layer coverage goal | At least 80%; tooling/report not established |

The similarity cutoff 0.35 is only a development proposal. Do not equate an operational health check with quality, availability or latency evidence.

## Live generation development check

Use canonical synthetic fixtures before a larger corpus. Include a supported fact, unrelated/unsupported question, genuinely conflicting evidence about the same fact and an instruction-injection example with legitimate support.

Require exact expected citation sets and valid structured results. Report provider timeout, unavailable service, malformed output, wrong answer, false abstention and skipped cases distinctly. The current harness measures expectation matches, not all factual claims; label review must supplement it.

Record all attempts, repetitions and failures under fixed parameters. Do not retry a stochastic model indefinitely until one pass appears, add fixture-specific heuristics or overwrite a failed run. Four smoke cases do not establish broad reliability.

## Result record

For every run retain:
- Source commit plus dirty-file/sanitized-snapshot fingerprints when applicable.
- Dataset/question/source IDs, label revision and development/held-out assignment.
- Model tag/digest, prompt version/hash, embedding/chunker/tokenizer revision, vector dimension and retrieval settings.
- Actual provider parameters, deadlines and context policy/limitations.
- Hardware, available RAM, runtime versions and concurrency.
- Raw input/output where safe, expected/actual outcomes and validation failures.
- Monotonic elapsed time for attempted cases; skipped cases have null latency and no measured inference.
- Cold/warm labels only when controlled and measured, not inferred from case order.
- Failure analysis, exclusions/denominators and exact reproduction commands.

Keep artifacts outside the source tree unless intentionally committing small safe fixtures. Redact credentials/full DB URLs and private content. Archive enough evidence for review, including failed attempts. Never manufacture a missing source fingerprint after a run.

## Integration and later evaluation

Hassan verifies actual migration, ingestion, filtered retrieval and API behavior; Naveed model quality; Zaid component states, accessibility, build and browser evidence. Their integration gate is the real upload-to-cited-answer/abstention flow.

Ruff, coverage, load and metric libraries need explicit dependency/configuration decisions. Do not run nonexistent scripts or claim CI from a YAML example. Governed-action checks follow the [security model](SECURITY_MODEL.md) in Phase 2.
