# KNEXUS team Git workflow

**Updated: 19 October 2026.** This guide and [CONTRIBUTING.md](../CONTRIBUTING.md) use the same default: short-lived feature branches and reviewed pull requests into `main`.

## Branches and ownership

- `main`: reviewed integration branch; keep the existing scaffold runnable.
- `feat/<member>-<feature>`: one feature or coherent milestone.
- `fix/<member>-<bug>`: a focused correction.
- `docs/<member>-<topic>`: documentation work.

Persistent `dev-hassan`, `dev-member2`, and `dev-member3` branches may be used as optional coordination branches when the team agrees. They are not required and do not replace focused PRs. Use normal merge commits when repeatedly integrating persistent branches, or recreate them from `main` after a squash merge to avoid replaying old changes.

The proposed module ownership is:

| Owner | Planned areas |
|---|---|
| Member 1 | `backend/app/services/ingestion/`, `services/retrieval/`, `core/`, `models/`, security integration |
| Member 2 | `backend/app/services/generation/`, `services/tools/`, prompts, evaluation |
| Member 3 | `frontend/`, `data/`, `docker/`, schema and data integration |

These service/model directories are not implemented yet. Consult [ARCHITECTURE.md](ARCHITECTURE.md) and agree on new paths before creating competing structures. Coordinate edits to shared settings, routes, dependencies, schemas, and Compose.

## Start a task

From a clean working tree:

```bash
git status
git switch main
git pull --ff-only origin main
git switch -c feat/yourname-feature
```

## Save and review changes

```bash
git diff
git add path/to/changed-file
git diff --cached
git commit -m "feat(rag): add document chunking"
git push -u origin feat/yourname-feature
```

Stage intentional files; inspect `.env`, credentials, large downloads, and generated artifacts before committing. Ignored files can still be explicitly force-added or remain tracked from earlier commits.

## Bring in changes from main

Commit or stash local work first, then:

```bash
git fetch origin
git merge origin/main
```

Explicit merging avoids depending on each developer's `git pull` merge/rebase configuration. Do not force-push shared branches. A rebase is an optional team decision for a private branch, not a required daily routine.

Branches reduce interference while editing but do not guarantee conflict-free integration. Conflicts can arise from overlapping edits, renames/deletions, binary files, or changes made at different times since the common ancestor. A fast-forward is possible only when one branch tip is an ancestor of the other; separate module ownership does not ensure it.

## Open a pull request

Push the branch and open the [KNEXUS pull-request page](https://github.com/Hassan092-prog/KNEXUS/pulls) with base `main`. Describe the resulting behavior, checks run, and known limitations. Request a teammate's review, resolve comments/conflicts, then merge using the repository's agreed method. Branch protection and CI are policies to configure; this repository does not currently contain an automated workflow.

## Resolve conflicts

```bash
git status
# Open conflicted files; reconcile both intended changes and remove conflict markers.
git add path/to/resolved-file
git merge --continue
# Re-run relevant checks, then push.
git push
```

Use `git merge --abort` if you need to return to the pre-merge state. For DOC/PPT/PDF binaries, choose or regenerate the correct artifact with its owner; Git cannot reconcile their content as plain text.

## Before merging

Confirm the scaffold still imports/starts when code changes, exercise affected routes, and add appropriate tests for new behavior. For docs, check links, commands, status claims, and consistency with source. There are currently no committed test or CI suites; do not describe proposed checks as passing automation.
