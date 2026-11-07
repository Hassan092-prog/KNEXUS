# KNEXUS Live Evaluation Protocol

## 1. Purpose and Authority
This protocol governs the live evaluation of KNEXUS generation and embedding services against external hosted provider APIs (Groq and Google AI Studio).

- Automated test runs, review tasks, and routine offline CI **MUST NEVER** execute live network provider calls.
- The project API expenditure budget is strictly **$0.00**; live evaluation is authorized exclusively for designated live smoke acceptance overseen by Hassan.

## 2. Execution Environment & Worktree Integrity
- **Clean Checkout Requirement**: Live evaluation runs **MUST** be executed from a fresh, isolated clean clone or git worktree checked out from merged `main` at an explicitly recorded commit hash (e.g. `/tmp/knexus-live-eval-$(git rev-parse --short main)`).
- **Prohibition on Dirty Checkouts**: Live runs **MUST NEVER** be run from the developer's original dirty checkout (`/home/hassan/Documents/Hassan/coding_projects/Major Project/KNEXUS`), which is on commit `b8414f2` (21+ commits behind `main`) and contains 71 uncommitted modified CRLF files.
- The environment must have a clean Python 3.12 virtual environment with installed dependencies and verified clean git status (`git status --porcelain` returns empty).

## 3. Configuration and Credentials
All provider credentials and execution parameters must be provided via server-side process environment variables. No secrets may ever be passed on command-line arguments or committed to git.

- **Groq API Key Setting**:
  The canonical `Settings` field in `backend/app/core/config.py` holding the Groq API key is:
  ```python
  GENERATION_API_KEY: SecretStr | None = None
  ```
  Set this via environment variable:
  ```bash
  export GENERATION_API_KEY="gsk_..."
  export GENERATION_PROVIDER="groq"
  export GENERATION_MODEL="llama-3.3-70b-versatile"
  ```

- **Quota Campaign Budgeting**:
  An explicit, non-default campaign identifier is strictly required:
  ```bash
  export QUOTA_CAMPAIGN_ID="eval-phase1-groq-<YYYYMMDD>"
  ```
  Silent fallbacks to `default` or empty campaigns are refused fail-closed by `validate_dispatch_campaign` before any HTTP client or socket is constructed.

## 4. Scheduled Harness Execution
1. The CLI evaluation harness (`backend/tests/phase1/generation/hosted_harness.py`) refuses to dispatch network calls based solely on CLI flags or credentials. Live dispatch requires reviewed code injection of an approved `DispatchPolicy` and `QuotaLedger` (via `get_generation_service`).
2. Output path **MUST** be fresh and non-existent; the harness refuses to overwrite historical result files:
   ```bash
   python -m tests.phase1.generation.hosted_harness \
     --run-live \
     --cases development \
     --output "results/hosted_eval_$(date +%Y%m%d_%H%M%S).jsonl"
   ```

## 5. Post-Execution Audit & Verification
After evaluation completes:
1. Inspect the resulting `.jsonl` records: verify all cases passed and exact citation sets match expected facts.
2. Confirm that no rate limits (HTTP 429) or timeouts were encountered.
3. Verify that the persistent quota state file (`quota_state.json`) accurately records settled attempts under the specified `QUOTA_CAMPAIGN_ID`.
