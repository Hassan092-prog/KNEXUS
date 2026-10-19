# KNEXUS team Git workflow: one branch per member

**Team model:** each of the three members has a persistent branch, commits and pushes their own work there, then opens a pull request into `main` when a feature is ready. Members do not push directly to `main`.

The names below follow the current team presentation. Change the branch labels if the team uses different names, but keep one stable branch per person.

| Member | Persistent branch | Primary ownership |
| --- | --- | --- |
| Hassan (Member 1) | `dev-hassan` | Backend, database/migrations, data/runtime, security and integration |
| Naveed (Member 2) | `dev-naveed` | LLM/prompt/citations, typed tools and answer evaluation |
| Zaid (Member 3) | `dev-zaid` | Entire frontend and UI verification |

Use [TEAM_RESPONSIBILITIES.md](TEAM_RESPONSIBILITIES.md) for member responsibilities and path ownership.

Each person should use their own clone of the repository. Do not share a single working directory: `git switch` changes the checkout for everyone using that directory.

## One-time setup

Install Git, then clone the repository and set your commit identity. Use the email connected to your GitHub account.

### Windows PowerShell

```powershell
git clone https://github.com/Hassan092-prog/KNEXUS.git
Set-Location KNEXUS
git config user.name "Your Name"
git config user.email "you@example.com"
git switch main
git pull --ff-only origin main
```

The three branches are already published. In a fresh personal clone, track **only your assigned branch**:

**Hassan (Member 1):**

```powershell
git switch --track origin/dev-hassan
```

**Naveed (Member 2):**

```powershell
git switch --track origin/dev-naveed
```

**Zaid (Member 3):**

```powershell
git switch --track origin/dev-zaid
```

GitHub may ask you to authenticate; use your normal Git credential manager. Never send teammates your password or personal access token.

### If your branch already exists on GitHub

Fetch it and track the remote branch; do not create a second branch with the same name:

```powershell
git fetch origin
git switch --track origin/dev-hassan
```

Replace the name with your own branch.

## Every work session

First check that you are on your own branch and have a clean working tree:

```powershell
git status --short --branch
git branch --show-current
```

Before a new task, bring in teammates' merged changes. Commit or stash any unfinished work first:

```powershell
git fetch origin
git switch dev-hassan
git merge --no-edit origin/main
git push
```

Replace `dev-hassan` with your branch. If `main` has no new commits, Git reports that it is already up to date.

After each reviewable task, inspect and push your work:

```powershell
git diff
git add path/to/your/changed-file
git diff --cached
git commit -m "feat(ingestion): parse PDF text"
git push
```

Commit small coherent tasks and push at the end of each work session. Stage named files rather than `git add .`; check for `.env`, credentials, downloaded corpora, model weights, and generated output before pushing. A branch is a collaboration boundary, not a backup for secrets.

## Integrate completed work

Use **one open pull request per member branch at a time**. Open a PR from your `dev-*` branch to `main`, ask a teammate to review, and describe behavior, checks, and limitations. Keep committing/pushing to update that same PR while it is under review.

Use a normal **merge commit** for each PR so Git records the member-branch commits as ancestors of `main`. This lets the same long-lived branch open later PRs without replaying previously merged commits. Do not squash or rebase-merge persistent member branches. If repository settings require squash-only merging, tell the team and switch together to short-lived feature branches for PRs; do not keep opening stale PRs from a squash-merged persistent branch.

After a PR is merged, continue from the same branch. At the beginning of the next task, merge current `origin/main` into it as shown above. Do not force-push or delete your persistent branch. The member branches are already published; see [TEAM_START.md](TEAM_START.md) for access and initial checkout status.

## Coordinate overlapping files

Branches isolate each person's local work; they do not prevent merge conflicts. Before editing shared interfaces such as `docker-compose.yml`, `backend/app/core/config.py`, API routes, dependency lists, migrations, or schema models, agree who owns the change. For Phase 1, use the task split in [PHASE_1_TEAM_GUIDE.md](PHASE_1_TEAM_GUIDE.md): Hassan (Member 1) owns models/migrations, data/runtime and routes/orchestration; Naveed (Member 2) owns prompt/generation and typed tool modules; Zaid (Member 3) owns the entire frontend. If a task needs another owner's file, agree on the contract and let its owner make the shared-file change, or coordinate one PR at a time.

Do not open multiple overlapping PRs for the same shared file. Review against `main`, sync your branch before resolving conflicts, and keep both members' intent. For a merge conflict:

```powershell
git status
# Edit conflicted files; remove conflict markers and preserve intended changes.
git add path/to/resolved-file
git commit
git push
```

For Office/PDF binary conflicts, coordinate with the file owner and select/regenerate the intended artifact; Git cannot merge their content as text.

## Protect the shared branch

Ask the repository admin to enable a GitHub rule for `main`: require pull requests and at least one teammate review; disallow force-push and branch deletion. Do not require CI checks until a real workflow exists. Members need write access to publish their own `dev-*` branches; a protected `main` should accept merges through PRs.

The [Phase 1 agent playbook](PHASE_1_TEAM_GUIDE.md) contains the numbered task sequence, file boundaries, completion checks and copyable start prompts for each developer agent.
