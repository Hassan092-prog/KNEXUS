# KNEXUS frontend

Only this README is committed in the merged baseline; no manifest, application source or build exists. [Project status](../docs/PROJECT_STATUS.md) records published work, not unpushed laptop progress.

Zaid owns the entire frontend. Use React and TypeScript; confirm Vite versus Next.js before scaffolding because neither is committed. Select compatible runtime/package versions and a lockfile.

Follow Z01-Z06 in the [playbook](../docs/PHASE_1_TEAM_GUIDE.md): scaffold, typed client/explicit mocks, upload/status screens, chat/citations/abstention, live integration and UI verification.

Use the [canonical schema and fixtures](../contracts/phase1/README.md). Do not invent wire fields or authoritative user/org/role identity. Render model text and excerpts safely. Generate in an empty temporary directory and adapt into this directory without deleting existing work. Document real install/dev/typecheck/test/build scripts only after they exist.

Keep mock/live mode visible. Distinguish loading, empty, queued, processing, complete, failed, answered and abstained states. Live failures remain errors. Stop polling on terminal states/unmount.

The browser calls Hassan's API, never Ollama. See [setup](../CONTRIBUTING.md) for tunneling. Login/admin/approval screens and streaming are later-phase work.
