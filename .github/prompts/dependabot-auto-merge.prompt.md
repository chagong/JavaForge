---
description: "Daily unattended Dependabot PR triage and safe-merge across the Microsoft-managed Java tooling repos. Consumed by the GitHub Copilot CLI in the dependabot-auto-merge workflow."
---

You are running unattended in a GitHub Actions job. There is NO human available
to answer questions. Your goal is to manage open Dependabot pull requests across
the Microsoft-managed Java tooling repositories listed below as autonomously as
possible — auditing, safely merging, and unblocking stuck PRs.

Follow the `dependabot-prs` skill at `.github/skills/dependabot-prs/SKILL.md`
(read it first) for the full workflow, safety criteria, and the catalog of
`@dependabot` comment commands. The rules below refine it for unattended runs.

**Tooling preference:** Use the GitHub MCP tools FIRST for every operation
(listing PRs, reading PR/check detail, reviewing, merging, commenting). Fall
back to the `gh` CLI (authenticated via `GH_TOKEN`) only when an MCP tool is
unavailable or fails. The `gh` commands shown below are fallbacks.

When in doubt about merging, do NOT merge — but still take a safe unblocking
action (e.g. ask Dependabot to rebase a conflicted PR) and report it.

## Repositories to process

- microsoft/vscode-java-debug
- microsoft/java-debug
- microsoft/vscode-java-test
- microsoft/vscode-gradle
- microsoft/build-server-for-gradle
- microsoft/vscode-java-dependency
- microsoft/vscode-maven
- microsoft/vscode-java-pack
- microsoft/vscode-spring-initializr
- microsoft/vscode-spring-boot-dashboard

## For each repository

1. List open Dependabot PRs (MCP tool preferred; `gh` fallback):

   ```
   gh pr list --repo OWNER/REPO --state open --search 'author:app/dependabot' --limit 100 --json number,title,url,headRefName,baseRefName,isDraft,mergeStateStatus,reviewDecision,updatedAt,statusCheckRollup
   ```

2. For every candidate PR, fetch full detail before deciding (MCP tool
   preferred; `gh` fallback):

   ```
   gh pr view PR_NUMBER --repo OWNER/REPO --json number,title,url,author,baseRefName,headRefName,isDraft,mergeStateStatus,reviewDecision,mergeable,changedFiles,additions,deletions,files,commits,statusCheckRollup
   ```

3. Poll CI until ALL workflows finish before deciding. Do NOT act on a PR while
   any check is `PENDING`, `IN_PROGRESS`, `QUEUED`, or `EXPECTED`. Re-fetch the
   PR's `statusCheckRollup` periodically (wait ~60s between polls) until every
   check run and status context has reached a terminal state
   (`SUCCESS` / `NEUTRAL` / `SKIPPED` / `FAILURE` / `CANCELLED` / `TIMED_OUT` /
   `ACTION_REQUIRED` / `STALE`). Only once the whole rollup is terminal do you
   evaluate the safety rules and take an action (merge, comment, or leave open).
   `gh` fallback for a single poll:

   ```
   gh pr view PR_NUMBER --repo OWNER/REPO --json statusCheckRollup,mergeStateStatus,mergeable
   ```

   If checks are still running after a reasonable number of polls, leave the PR
   open, note it as "CI still in progress", and let the next scheduled run pick
   it up. After approving or after a `@dependabot rebase`/`recreate` (which
   re-triggers CI), poll again until all workflows complete before merging.

   CI workflows sometimes fail intermittently. When polling finishes and one or
   more checks ended in `FAILURE` / `CANCELLED` / `TIMED_OUT`, re-run the failed
   jobs ONCE before treating the failure as real. Identify the run from the
   failed check and re-run only its failed jobs:

   ```
   gh run rerun RUN_ID --repo OWNER/REPO --failed
   ```

   Then poll again until the rerun reaches a terminal state. If it is still red
   after this single rerun, treat the failure as real: do NOT merge, leave the
   PR open, and report it. Re-run the failed jobs at most once per PR per run.

## Safety rules — a PR is SAFE to merge ONLY when ALL are true

- Author is `app/dependabot` or `dependabot[bot]`.
- The PR is not a draft.
- `mergeable` is `MERGEABLE`.
- `mergeStateStatus` is `CLEAN`, or `BLOCKED` solely because a required review is
  missing while every required check is green.
- Every check run is `COMPLETED` with conclusion `SUCCESS`, `NEUTRAL`, or
  `SKIPPED`; every status context is `SUCCESS`. No `FAILURE`, no `PENDING`, no
  `IN_PROGRESS`, no `QUEUED`, no missing required checks.
- The diff touches ONLY dependency manifests and lockfiles
  (`package.json`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`,
  `pom.xml`, `build.gradle`, `gradle.lockfile`, `*.gradle`, etc.). No source
  code, workflow, or configuration changes beyond the dependency bump.
- The update is LOW RISK: a patch or minor version bump. Treat the leading
  semver component: if the major version increases, it is NOT low risk.

## Do NOT merge (leave open and report) when

- It is a MAJOR version bump (e.g. `6.x -> 7.x`, `20.x -> 25.x`).
- Any check is failing, pending, in progress, queued, or missing.
- `mergeStateStatus` is `DIRTY` / the branch has conflicts.
- The diff changes source code, CI workflows, or anything beyond manifests and
  lockfiles.
- Provenance or scope is unclear in any way.

## Merge procedure for SAFE PRs

Process one PR at a time. After each merge, the base branch moves, so RE-AUDIT
the remaining PRs in that repo before merging the next one. Prefer MCP review /
merge tools; the `gh` commands below are fallbacks.

1. Approve:

   ```
   gh pr review PR_NUMBER --repo OWNER/REPO --approve --body 'Approved: automated Dependabot triage — low-risk dependency update with green checks.'
   ```

2. Refresh state (branch protection may recalculate; `mergeStateStatus` may
   briefly be `UNKNOWN` — re-check until it settles):

   ```
   gh pr view PR_NUMBER --repo OWNER/REPO --json mergeStateStatus,mergeable,reviewDecision,statusCheckRollup
   ```

3. Merge ONLY if the refreshed state is `CLEAN` / `MERGEABLE` / `APPROVED` with
   all checks green. If approval (or any rebase/recreate) re-triggered CI, poll
   again per step 3 above until every workflow is terminal before merging:

   ```
   gh pr merge PR_NUMBER --repo OWNER/REPO --squash --delete-branch
   ```

## Proactively unblock PRs that are NOT mergeable yet

Do as much as you safely can to move every Dependabot PR forward. Use the
`@dependabot` comment commands from the `dependabot-prs` skill (post via the MCP
issue-comment tool, or `gh pr comment PR_NUMBER --repo OWNER/REPO --body '...'`
as a fallback). Match the command to the PR state:

| PR state | Action |
|----------|--------|
| Conflicted / `DIRTY` merge state | Comment `@dependabot rebase`. If the branch is stale after a rebase and no human edits exist, `@dependabot recreate`. |
| Superseded / obsolete duplicate update already covered by a newer PR | Comment `@dependabot recreate` on the newest one; leave older ones for the next run. |
| Major bump you decide to defer (NOT auto-merge) | Leave it open and report. Do NOT `ignore`/`close` it — those discard the update permanently and need human intent. |

Prefer direct approve + merge for clearly safe PRs. Use `@dependabot rebase` /
`recreate` to unblock the rest. When CI ends red, re-run the failed jobs once
(see step 3) to absorb intermittent failures; if it is still red after that
single rerun, leave the PR for a later run.

## Guardrails

- Never merge a PR that fails any safety rule above (major bump, red/pending
  checks, conflicts, non-manifest diff, unclear provenance).
- Do NOT use `@dependabot ignore` or `@dependabot close` — those permanently
  discard updates and require human intent.
- Do NOT edit repository files, push commits, or change branch protection.

## Final report

Print a concise summary with:

- Each repository checked.
- PRs approved and merged, with URLs.
- PRs left open, each with a one-line reason (major bump, failing checks,
  pending checks, conflicts, non-manifest diff, etc.).
- Any `@dependabot` commands posted (rebase / recreate), with
  the PR URL and why.

## Send a Teams notification with the result

After printing the report, use the `send-teams-notification` skill at
`.github/skills/send-teams-notification/SKILL.md` to deliver the same summary to
Teams. 

- Send ONE notification per recipient: split `RECIPIENTS` on commas/semicolons,
  trim whitespace, and POST the payload once per email address.
- Build a Markdown `message` from the report above: counts of merged / left-open
  PRs per repo, the merged PR URLs, the left-open PRs with reasons, and any
  `@dependabot` commands posted. Keep it concise.
- Use a `title` like `Dependabot triage — <N> merged, <M> open (<date>)`.
- If `PERSONAL_NOTIFICATION_URL` or `RECIPIENTS` is empty, skip the notification
  and note that in the printed report instead of failing.
