# KNEXUS Frontend

**Current state (19 October 2026):** this README is the only tracked frontend file. There is no `package.json`, application source, dev server, or build command yet. The screens below are planned.

This directory is designated for the user-facing interface built with **React**, **TypeScript**, and **Vite**.

## Owner and delivery plan

**Zaid (Member 3), branch `dev-zaid`, owns the entire frontend**: React/TypeScript/Vite setup, components/pages, API client/types, mock payloads, upload/chat/citation/abstention states, login/admin/approval screens, accessibility and UI checks. Frontend work starts in Phase 1 against agreed typed mocks, then connects to Hassan's APIs; Phase 2 completes protected/admin/approval screens and Phase 3 focuses on integration/usability.

Follow [TEAM_RESPONSIBILITIES.md](../docs/TEAM_RESPONSIBILITIES.md) for the member responsibilities. Hassan owns backend/schema/migrations/data/runtime; Naveed owns LLM/prompt/citation behavior. Zaid consumes their accepted contracts. No frontend manifest, source or live API client exists yet.

## Planned Capabilities
- **Knowledge Chat Interface:** Streaming token display, citation cards, abstention indicators.
- **Document Management Panel:** Drag-and-drop document upload, parsing status, permission tags.
- **Human-in-the-Loop Approval UI:** Pending action proposals, diff view, approve/reject controls.
- **Admin Dashboard:** Role assignment, organization settings, system health metrics.

## Phase 1 initialization precautions

`frontend/` is not empty because this README already exists. Generate the agreed React/TypeScript scaffold in an empty temporary directory, then bring the generated application/configuration files into `frontend/` while preserving this README. Review the file changes before committing; do not approve a generator option that deletes the existing directory contents.

Check the selected generator's Node.js requirements on Zaid's own machine. Commit the selected package versions and lockfile with the scaffold, and document the actual install/dev/build commands after `package.json` exists. There is no valid frontend build to run before that task is completed.
