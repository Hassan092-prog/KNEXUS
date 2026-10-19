# Evaluation & Testing Strategy

> **Implementation status - 19 October 2026:** This document describes the target design and acceptance criteria. Only the backend scaffold, dependency health route, and PostgreSQL/pgvector bootstrap are implemented. See [REPOSITORY_REVIEW.md](REPOSITORY_REVIEW.md) for current behavior and known gaps. Code examples, proposed directories, tests, and migrations below are not evidence of completed work.

## KNEXUS: Knowledge Network for EXploration and Unified Services
**Version:** 1.0 | **Status:** Active | **Last Updated:** October 2026

---

## 1. Overview

KNEXUS evaluation spans three dimensions:

1. **RAG Quality** — How accurately does the system retrieve and generate knowledge-grounded answers?
2. **Security & Access Control** — Does the system enforce RBAC and multi-tenancy without exception?
3. **System Quality** — Is the software correct, fast, and maintainable?

---

## 2. Datasets

### 2.1 Primary: EnterpriseRAG-Bench

**Source:** [Official repository](https://github.com/onyx-dot-app/EnterpriseRAG-Bench) and [Hugging Face dataset](https://huggingface.co/datasets/onyx-dot-app/EnterpriseRAG-Bench). Record the imported revision and license in the future manifest.

Simulates a fictional company ("Redwood Inference") with realistic enterprise data:

| Source Type | Record Count | Content |
|---|---|---|
| Slack | 285,605 | Channel conversations, announcements |
| Gmail | 121,390 | Email threads, attachments |
| Linear | 35,308 | Engineering issue tracker |
| Google Drive | 25,108 | Documents, policies, SOPs |

**Subset used for KNEXUS:** 1,000–2,000 curated records across all four source types.

### 2.2 Evaluation QA Set (500 Questions)

| Category | Count | Description |
|---|---|---|
| Basic factual | 175 | Single-document, single-fact answers |
| Semantic inference | 125 | Answers require paraphrasing or inference |
| Intra-document reasoning | 40 | Multi-section answers from one document |
| Project-related | 40 | Questions tied to project-specific context |
| Constrained | 30 | Qualifiers disambiguate evidence; RBAC labels are added separately |
| Conflicting information | 20 | Two documents give contradictory answers |
| Completeness | 20 | Full answer requires multiple documents |
| Miscellaneous | 20 | Informal, off-topic, or loosely organized records |
| High-level synthesis | 10 | Abstract summary questions |
| Information-not-found | 20 | Correct answer is "Evidence not found" (abstention) |
| **Total** | **500** | Published category breakdown |

### 2.3 KNEXUS Synthetic Security Fixtures

Custom-designed test fixtures covering:
- **Roles defined:** `superadmin`, `orgadmin`, `manager`, `employee`
- **Multi-tenant orgs:** Org A (Redwood Inference) + Org B (custom)
- **Documents with mixed permissions:** some `employee`, some `manager+`, some `orgadmin` only
- **Security test QA pairs:** 6 key scenarios (see Security Model doc)
- **Tool execution scenarios:** create, update, reject, expire, tamper

---

## 3. RAG Evaluation Metrics

### 3.1 Retrieval Metrics

| Metric | Formula | Target |
|---|---|---|
| **Recall@K** | Relevant chunks retrieved / Total relevant chunks | ≥ 0.70 @ K=5 |
| **Precision@K** | Relevant chunks retrieved / K chunks retrieved | >= 0.70 @ K=5 |
| **MRR (Mean Reciprocal Rank)** | Average of 1/rank of first relevant chunk | ≥ 0.75 |
| **Abstention Accuracy** | Correct abstentions / Total abstention-expected queries | ≥ 0.90 |

### 3.2 Generation Metrics

| Metric | Measurement Method | Target |
|---|---|---|
| **Citation Accuracy** | % of citations that map to a real, correct source chunk | ≥ 0.85 |
| **Faithfulness** | % of answer claims grounded in retrieved context (human/LLM judge) | ≥ 0.80 |
| **Answer lexical overlap (proxy)** | ROUGE-L against gold answers; supplement with human correctness/support review | ≥ 0.55 |
| **Hallucination Rate** | % of answers containing claims not in context | ≤ 0.10 |

### 3.3 End-to-End Metrics

| Metric | Target |
|---|---|
| Full pipeline accuracy | ≥ 70% on the 500-question benchmark |
| Abstention rate on info-not-found set | ≥ 90% |
| RBAC enforcement | 100% (zero leakage in security fixture suite) |

---

### Dataset and scoring boundaries

The category counts sum to 500; KNEXUS fixtures are additional. Source counts above are historical figures from the bundled PDF, not a pinned download inventory. Upstream publishes approximate volumes; record exact counts from the imported revision.

A curated 1,000-2,000-record subset cannot be assumed to contain evidence for all questions. Build a source-ID coverage manifest, retain distractors, and report subset and full-corpus scores separately. Split development/tuning and held-out questions before choosing thresholds or prompts. Distinguish gold document IDs from chunk IDs; deduplicate retrieved documents for document-level metrics. Skip retrieval recall/MRR where no gold documents exist (High Level and Info Not Found), reporting denominators explicitly. Add permission-aware labels separately; Constrained questions are not an RBAC benchmark.

Report false abstentions on answerable questions as well as correct abstentions on missing evidence. Version dataset, model, tokenizer/chunker, prompt, embedding dimension, retrieval parameters, and hardware/load with each result. A similarity threshold of 0.35 is an uncalibrated starting proposal.

## 4. Test Pyramid

```
                          ┌──────────────┐
                          │  RAG Eval    │  ← 500-question benchmark
                          │  (Automated) │    Security fixture suite
                          └──────┬───────┘
                        ┌────────▼────────┐
                        │  Integration    │  ← E2E user journeys
                        │  Tests          │    DB + API + pipeline
                        └────────┬────────┘
               ┌─────────────────▼──────────────────┐
               │           Unit Tests                │  ← Service functions
               │      (pytest + pytest-asyncio)      │    Utility functions
               └────────────────────────────────────┘
```

---

## Current validation versus planned tests

No test files, benchmark harness, CI workflow, load script, or fixtures are committed. Snippets below are illustrative and need implementations/imports/fixtures before execution. `pytest`, `pytest-asyncio`, and `httpx` are declared dependencies; Ruff, Locust, ROUGE/RAGAS, and coverage tooling are not. The draft CI workflow also needs tool installation, database readiness/extension initialization, configuration, and actual tests before enabling it.

## 5. Unit Tests

### 5.1 Ingestion Service
```python
# tests/unit/test_chunker.py
def test_recursive_chunker_respects_max_tokens():
    chunker = RecursiveChunker(chunk_size=240, overlap=32)
    text = "..." * 1000
    chunks = chunker.split(text)
    assert all(len(embedding_tokenizer.encode(c)) <= 256 for c in chunks)  # Includes special tokens

def test_chunker_overlap_is_applied():
    chunks = chunker.split(long_text)
    # Verify last 32 tokens of chunk[0] appear at start of chunk[1]
    ...

def test_pdf_parser_extracts_metadata():
    doc = PdfParser.parse("tests/fixtures/expense_policy.pdf")
    assert doc.title is not None
    assert doc.page_count > 0
    assert len(doc.text) > 100
```

### 5.2 Embedding Service
```python
def test_embedder_output_shape():
    embedder = SentenceTransformerEmbedder("all-MiniLM-L6-v2")
    vectors = embedder.encode(["Hello world"])
    assert vectors.shape == (1, 384)

def test_embedder_deterministic():
    v1 = embedder.encode(["Test sentence"])
    v2 = embedder.encode(["Test sentence"])
    assert np.allclose(v1, v2)
```

### 5.3 LLM & Prompt Service
```python
def test_prompt_builder_injects_context():
    prompt = PromptBuilder.build(
        question="What is the leave policy?",
        chunks=[ChunkContext(content="Annual leave: 21 days", doc_title="HR Policy")]
    )
    assert "<context>" in prompt
    assert "Annual leave: 21 days" in prompt
    assert "What is the leave policy?" in prompt

def test_prompt_builder_handles_empty_context():
    prompt = PromptBuilder.build(question="...", chunks=[])
    assert "Evidence not found" in prompt or "no context" in prompt.lower()
```

### 5.4 Auth & Security
```python
def test_jwt_token_contains_required_claims():
    token = create_access_token(user_id="uuid", org_id="uuid", role="employee")
    payload = decode_token(token)
    assert "sub" in payload
    assert "org_id" in payload
    assert "role" in payload
    assert payload["exp"] > time.time()

def test_bcrypt_hash_and_verify():
    hashed = hash_password("securepass123")
    assert verify_password("securepass123", hashed)
    assert not verify_password("wrongpass", hashed)
```

---

## 6. Integration Tests

### 6.1 FastAPI Endpoint Tests

```python
# tests/integration/test_query_endpoint.py
@pytest.mark.asyncio
async def test_query_returns_answer_with_citations(async_client, authenticated_headers):
    # Setup: insert test document + embeddings into test DB
    # Act
    response = await async_client.post(
        "/api/v1/query",
        json={"question": "What is the expense limit?"},
        headers=authenticated_headers(role="employee")
    )
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["abstained"] == False
    assert len(data["citations"]) > 0
    assert data["answer"] is not None

@pytest.mark.asyncio
async def test_query_abstains_on_missing_evidence(async_client, authenticated_headers):
    response = await async_client.post(
        "/api/v1/query",
        json={"question": "What is the location of the secret server room?"},
        headers=authenticated_headers(role="employee")
    )
    assert response.status_code == 200
    assert response.json()["abstained"] == True
```

### 6.2 RBAC Integration Tests

```python
@pytest.mark.asyncio
async def test_employee_cannot_access_manager_only_document(async_client):
    # Upload doc with allowed_roles = ["manager"]
    # Login as employee
    response = await async_client.post(
        "/api/v1/query",
        json={"question": "What is the manager salary band?"},
        headers=employee_headers
    )
    assert response.json()["abstained"] == True  # Not forbidden — just no evidence

@pytest.mark.asyncio
async def test_cross_tenant_isolation(async_client):
    # Org A employee queries for Org B's document
    response = await async_client.get(
        f"/api/v1/documents/{org_b_doc_id}",
        headers=org_a_employee_headers
    )
    assert response.status_code == 404  # Not 403 — don't leak existence
```

---

## 7. RAG Benchmark Harness

### 7.1 Evaluation Script (`tests/evaluation/run_benchmark.py`)

```python
"""
KNEXUS 500-Question Benchmark Evaluation Harness
Proposed invocation once implemented: python -m pytest tests/evaluation/ -v
No --benchmark option/plugin is currently configured.
"""

BENCHMARK_QA_PATH = "data/evaluation/knexus_500q_benchmark.json"

@pytest.mark.asyncio
async def test_rag_benchmark_full():
    qa_pairs = load_json(BENCHMARK_QA_PATH)
    results = []

    for qa in qa_pairs:
        response = await query_api(qa["question"])
        result = {
            "question": qa["question"],
            "category": qa["category"],
            "expected_abstain": qa.get("abstain", False),
            "actual_abstain": response["abstained"],
            "answer": response["answer"],
            "citations": response["citations"],
            "gold_source_ids": qa.get("source_ids", []),
        }
        results.append(result)

    metrics = compute_metrics(results)
    print_report(metrics)

    # Hard assertions
    assert metrics["precision_at_5"] >= 0.70
    assert metrics["recall_at_5"] >= 0.70
    assert metrics["abstention_accuracy"] >= 0.90
```

### 7.2 Evaluation Report Format

After implementing and running the benchmark, generate a structured report. **The numbers below are illustrative placeholders, not measured KNEXUS results:**

```markdown
## KNEXUS RAG Evaluation Report
**Date:** 2026-XX-XX | **Model:** llama3.2 | **Embedding:** all-MiniLM-L6-v2

| Metric | Score | Target | Status |
|---|---|---|---|
| Precision@5 | 0.72 | >= 0.70 | ✅ |
| Recall@5 | 0.74 | ≥ 0.70 | ✅ |
| MRR | 0.81 | ≥ 0.75 | ✅ |
| Citation Accuracy | 0.88 | ≥ 0.85 | ✅ |
| Abstention Accuracy | 0.92 | ≥ 0.90 | ✅ |
| Hallucination Rate | 0.07 | ≤ 0.10 | ✅ |

### Failure Analysis
- Category with lowest performance: Conflicting Information (0.55)
- Root cause: Model tends to pick the most recent chunk, ignoring the conflict
- Proposed fix: Add explicit conflict-detection in system prompt
```

---

## 8. Performance Benchmarks

### Latency Testing
```bash
# Using locust for load testing
locust -f tests/load/locustfile.py --host http://localhost:8000 --users 20 --spawn-rate 5
```

```python
# tests/load/locustfile.py
from locust import HttpUser, task, between

class KnexusUser(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def query_knowledge(self):
        self.client.post(
            "/api/v1/query",
            json={"question": "What is the annual leave policy?"},
            headers=self.auth_headers
        )

    @task(1)
    def list_documents(self):
        self.client.get("/api/v1/documents", headers=self.auth_headers)
```

**Pass criteria:** p95 latency ≤ 12s under 20 concurrent users.

---

## 9. CI/CD Test Pipeline

```yaml
# .github/workflows/test.yml
name: KNEXUS Test Suite

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_DB: knexus_test
          POSTGRES_USER: knexus_admin
          POSTGRES_PASSWORD: test_password
        ports: ["5435:5432"]

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r backend/requirements.txt
      - run: cd backend && ruff check .        # Linting
      - run: cd backend && ruff format --check . # Format check
      - run: cd backend && pytest tests/unit/ -v              # Unit tests
      - run: cd backend && pytest tests/integration/ -v       # Integration tests
```

---

*KNEXUS Evaluation & Testing Strategy v1.0 | MJCET CSE (AI&ML) | Team 3 | 2026–2027*
