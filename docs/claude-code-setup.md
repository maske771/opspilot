# Claude Code setup for OpsPilot

This guide configures Claude Code on the developer workstation. It does not store API keys in the repository.

## 1. Prerequisites

- Windows 10/11 with Git for Windows
- Node.js LTS and npm
- Git access to `maske771/opspilot`
- Docker Desktop for local verification when available

## 2. Install Claude Code

Install Claude Code using the current official Anthropic installation instructions. Keep authentication local to the workstation and never add credentials to `.env`, Git, issues, or pull requests.

## 3. Prepare the repository

```powershell
cd C:\Users\User
if (-not (Test-Path .\opspilot)) { git clone https://github.com/maske771/opspilot.git }
cd .\opspilot
git fetch origin
git switch feature/mvp-foundation
git pull --ff-only origin feature/mvp-foundation
```

If local work exists, preserve it and inspect `git status` before switching branches.

## 4. Start Claude Code

From the repository root:

```powershell
claude
```

The agent should automatically load the root `CLAUDE.md` and project-level `.claude/settings.json`.

## 5. First session prompt

Use this prompt for the first run:

> Read CLAUDE.md, docs/product-spec.md, docs/architecture.md, docs/api.md, docs/ai-agents.md, and the current git status. Do not change files yet. Produce a concise repository health report: architecture, working features, failing or unverified areas, security risks, test status, and the next three implementation tasks. Inspect actual files and commands; do not guess.

## 6. Implementation prompt

For an approved task:

> Implement this task in OpsPilot: [describe the task]. Investigate the relevant code first, make the smallest complete change, add or update tests, run focused verification, review the diff for secrets and tenant isolation, and report exact results. Do not stop at recommendations.

## Operating rules

- Keep `.env` local and untracked.
- Use feature branches for changes.
- Never use force push or destructive database commands without explicit approval.
- Prefer a pull request for reviewable changes.
- Treat green tests as evidence for the tested scope, not proof of production readiness.
