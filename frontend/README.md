# KNEXUS frontend

## Source adaptation and hosted boundary

Inspect reusable components from [enterprise-knowledge-bot at the pinned revision](https://github.com/Hassan092-prog/enterprise-knowledge-bot/tree/e67771a15f49a79443a365fbce85b8559ef43fb7), redesign the UI and adapt to canonical KNEXUS payloads. Preserve licences, authorship and local work; do not copy old API/role assumptions, secrets or unrelated modules.

Generation and embeddings use backend-held hosted API credentials under the revised plan; adapters are pending. No provider keys or direct provider requests in browser code. Mock mode remains explicit and never hides live failures.

Only this README is committed in the merged baseline; no manifest, application source or build exists. [Project status](../docs/PROJECT_STATUS.md) records published work, not unpushed laptop progress.

Zaid owns the entire frontend. Use React and TypeScript; confirm Vite versus Next.js before scaffolding because neither is committed. Select compatible runtime/package versions and a lockfile.

Follow Z01-Z06 in the [playbook](../docs/PHASE_1_TEAM_GUIDE.md): scaffold, typed client/explicit mocks, upload/status screens, chat/citations/abstention, live integration and UI verification.

Use the [canonical schema and fixtures](../contracts/phase1/README.md). Do not invent wire fields or authoritative user/org/role identity. Render model text and excerpts safely. Generate in an empty temporary directory and adapt into this directory without deleting existing work. Document real install/dev/typecheck/test/build scripts only after they exist.

Keep mock/live mode visible. Distinguish loading, empty, queued, processing, complete, failed, answered and abstained states. Live failures remain errors. Stop polling on terminal states/unmount.

The browser calls Hassan's backend, never hosted providers. No local model setup is required. Any approved browser-to-backend SSH forward is separate from retired model tunnels; see [setup](../CONTRIBUTING.md). Login/admin/approval screens and streaming are later-phase work.
