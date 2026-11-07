# Phase 1 shared contract reference

**Version 0.1 - initial baseline merged in [PR #1](https://github.com/Hassan092-prog/KNEXUS/pull/1).** This folder gives Hassan, Naveed and Zaid concrete inputs/outputs to review before integrating their implementations. It registers no FastAPI routes and creates no database tables.

- [Implementation baseline](../../docs/PHASE_1_CONTRACT.md): scope, HTTP behavior, service/data boundaries and deferred work.
- [models.py](models.py): authoritative reference types and cross-field invariants using the project's existing Pydantic dependency.
- [schema.json](schema.json): generated JSON Schema for frontend tooling and shape inspection. Python cross-field/membership validators are additional requirements not fully expressible in this export.
- [examples/manifest.json](examples/manifest.json): maps every synthetic fixture to its model.
- [Setup and Git workflow](../../CONTRIBUTING.md): environments, branches and inference.

Run from the repository root with the backend environment:

```bash
backend/venv/bin/python contracts/phase1/check.py
```

PowerShell:

```powershell
./backend/venv/Scripts/python.exe contracts/phase1/check.py
```

The checker needs no database, Ollama, frontend or additional dependency beyond Pydantic. It validates all fixtures, rejects invalid/adversarial contract cases, checks cited IDs against supplied evidence and checks the schema export matches the reference models. It does not prove authentication, authorized retrieval, claim support or working application endpoints.

If a reviewed model change or Pydantic dependency upgrade changes schema generation, regenerate and review the JSON diff:

```bash
backend/venv/bin/python contracts/phase1/check.py --write-schema
```

All examples are synthetic; timing values of zero and similarity values are illustrative, not evaluation results. Files ending in `query-*`, `document-*`, `upload-*` and `*-error` are HTTP-boundary mocks. `generation-*` are the internal backend/generator boundary. `actor-context.json` is server-controlled fixture identity, never a client payload.

Backend code imports canonical classes through app.schemas; do not duplicate them. Generation boundaries, persistence and document/query HTTP routes are implemented; hosted generation transport (PR #13), offline embedding foundation (PR #16), and hosted input token validation (PR #19) are merged, while API wiring, live token correspondence, and live acceptance remain pending under [TRD](../../docs/TRD.md). Provider migration preserves canonical fields. Update the reference, export, fixtures and callers together when the accepted contract changes.
