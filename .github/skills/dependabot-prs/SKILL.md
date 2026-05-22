---
name: dependabot-prs
description: "Manage GitHub Dependabot pull requests. Use when: listing Dependabot PRs, checking whether dependency update PRs are safe to merge, approving or merging safe Dependabot PRs, rebasing or recreating Dependabot PRs, closing or ignoring dependency updates, using @dependabot comment commands, triaging grouped Dependabot updates. Input: repo owner/name, repo URL, workspace repo name, or a set of Java tooling repos; optional action such as audit, merge-safe, rebase, recreate, ignore, unignore, show-ignore-conditions."
argument-hint: 'owner/repo action, e.g. "microsoft/vscode-maven audit" or "microsoft/vscode-java-pack merge-safe"'
---

# Dependabot Pull Requests

Manage Dependabot-authored pull requests by combining GitHub PR metadata, CI status, review/merge operations, and Dependabot comment commands.

## When to Use

- List open Dependabot pull requests for one repo or the Microsoft Java tooling repos.
- Decide whether Dependabot PRs are safe to approve and merge.
- Approve and merge green, low-risk Dependabot PRs when the user asks.
- Ask Dependabot to rebase, recreate, merge later, squash-and-merge later, cancel a queued merge, reopen, close, ignore, unignore, or show ignore conditions.
- Triage grouped Dependabot version or security update PRs.

## Repository Scope

Accept any of:

- `owner/repo`, for example `microsoft/vscode-gradle`
- A GitHub PR or repository URL
- A local workspace repository folder name from `.github/copilot-instructions.md`
- "Java tooling repos under microsoft", meaning these Microsoft-owned repos:
  - `microsoft/vscode-java-debug`
  - `microsoft/java-debug`
  - `microsoft/vscode-java-test`
  - `microsoft/vscode-gradle`
  - `microsoft/build-server-for-gradle`
  - `microsoft/vscode-java-dependency`
  - `microsoft/vscode-maven`
  - `microsoft/vscode-java-pack`
  - `microsoft/vscode-spring-initializr`
  - `microsoft/vscode-spring-boot-dashboard`

## Core Workflow

### 1. List Dependabot PRs

Use GitHub PR search or `gh`:

```powershell
gh pr list --repo OWNER/REPO --state open --search 'author:app/dependabot' --limit 100 --json number,title,url,headRefName,baseRefName,isDraft,mergeStateStatus,reviewDecision,updatedAt,statusCheckRollup
```

If the user asks for multiple repositories, run the query per repo and present a compact table with:

- repo
- PR number and URL
- title
- draft status
- merge state
- review decision
- failing, pending, or missing required checks
- recommended action

### 2. Inspect Candidate PRs Before Approving or Merging

For any PR that appears green, inspect its changed files and commits:

```powershell
gh pr view PR_NUMBER --repo OWNER/REPO --json number,title,url,author,baseRefName,headRefName,isDraft,mergeStateStatus,reviewDecision,mergeable,changedFiles,additions,deletions,files,commits,statusCheckRollup
```

A PR is normally safe to approve and merge only when all of these are true:

- Author is `app/dependabot` or `dependabot[bot]`.
- PR is not a draft.
- `mergeable` is `MERGEABLE`.
- `mergeStateStatus` is `CLEAN`, or it is `BLOCKED` only because review is required and all required checks are green.
- Every `CheckRun` is `COMPLETED` with conclusion `SUCCESS`, `NEUTRAL`, or `SKIPPED`.
- Every `StatusContext` has state `SUCCESS`.
- The diff is limited to dependency manifests, lockfiles, or generated dependency metadata expected for the ecosystem.
- The update is low risk: patch/minor lockfile refreshes are usually low risk; major framework/toolchain/runtime updates are not automatically safe.

Do not approve or merge when the PR is dirty/conflicted, has failed or pending required checks, changes source code unexpectedly, includes a major or risky runtime update, has unresolved review comments, or has unclear provenance. Report the blocker instead.

### 3. Approve and Merge Safe PRs

When the user explicitly asks to approve and merge safe Dependabot PRs:

1. Approve only after the inspection above.
2. Refresh PR state after approval because branch protection may recalculate.
3. Merge only if the refreshed state is clean, approved, mergeable, and green.

Using `gh`:

```powershell
gh pr review PR_NUMBER --repo OWNER/REPO --approve --body 'Approved: Dependabot dependency update with green checks.'
gh pr view PR_NUMBER --repo OWNER/REPO --json mergeStateStatus,mergeable,reviewDecision,statusCheckRollup
gh pr merge PR_NUMBER --repo OWNER/REPO --squash --delete-branch
```

Using MCP GitHub tools, call the review/merge tools for the same steps when available. Prefer squash merges for Dependabot PRs unless the repository convention or user request says otherwise.

### 4. Use Dependabot Comment Commands

Dependabot responds to commands posted as PR comments. Use `gh pr comment` or a GitHub PR comment tool.

```powershell
gh pr comment PR_NUMBER --repo OWNER/REPO --body '@dependabot rebase'
```

Use these commands for ordinary Dependabot PRs:

| Command | Effect |
|---------|--------|
| `@dependabot cancel merge` | Cancels a previously requested Dependabot merge. |
| `@dependabot close` | Closes the PR and prevents Dependabot from recreating that exact PR. |
| `@dependabot ignore this dependency` | Closes the PR and prevents future PRs for that dependency unless reopened or manually upgraded. |
| `@dependabot ignore this major version` | Closes the PR and ignores updates for this major version. |
| `@dependabot ignore this minor version` | Closes the PR and ignores updates for this minor version. |
| `@dependabot ignore this patch version` | Closes the PR and ignores updates for this patch version. |
| `@dependabot merge` | Asks Dependabot to merge once CI passes. |
| `@dependabot rebase` | Asks Dependabot to rebase the PR. |
| `@dependabot recreate` | Recreates the PR and overwrites edits made to the PR. Confirm before using if humans edited the branch. |
| `@dependabot reopen` | Reopens a closed Dependabot PR. |
| `@dependabot show DEPENDENCY_NAME ignore conditions` | Shows stored ignore conditions for a dependency. |
| `@dependabot squash and merge` | Asks Dependabot to squash and merge once CI passes. |

For grouped version update and grouped security update PRs, use dependency-specific commands:

| Command | Effect |
|---------|--------|
| `@dependabot ignore DEPENDENCY_NAME` | Closes the PR and prevents updates for that dependency. |
| `@dependabot ignore DEPENDENCY_NAME major version` | Ignores major-version updates for that dependency. |
| `@dependabot ignore DEPENDENCY_NAME minor version` | Ignores minor-version updates for that dependency. |
| `@dependabot ignore DEPENDENCY_NAME patch version` | Ignores patch-version updates for that dependency. |
| `@dependabot unignore *` | Closes the current PR, clears all ignore conditions for all dependencies in the group, and opens a new PR. |
| `@dependabot unignore DEPENDENCY_NAME` | Clears ignore conditions for one dependency and opens a new PR with available updates for it. |
| `@dependabot unignore DEPENDENCY_NAME IGNORE_CONDITION` | Clears one stored ignore condition and opens a new PR with matching available updates. |

Before using an ignore or unignore command, explain its persistence and blast radius. For a specific stored condition, first run:

```text
@dependabot show DEPENDENCY_NAME ignore conditions
```

### 5. Recommended Actions by State

| State | Action |
|-------|--------|
| Clean, green, lockfile-only, low-risk | Approve and merge if requested. |
| Blocked only by required review | Approve, refresh, then merge if state becomes clean. |
| Dirty/conflicted | Use `@dependabot rebase`; if that fails or stale generated files remain, consider `@dependabot recreate` after confirming no manual edits should be preserved. |
| Failed checks | Read failing check logs before taking action; do not merge. |
| Pending checks | Wait or re-check later; do not merge. |
| Major dependency/framework update | Summarize risk and ask before merging unless the user explicitly allowed major updates. |
| Unwanted update | Use the narrowest ignore command that matches the user's intent. |

## Reporting

In the final response, include:

- Repos checked.
- PRs approved and merged, with URLs.
- PRs left open, with concrete reasons such as failed checks, dirty merge state, risky update, or needing user confirmation.
- Any Dependabot comment commands posted.

Do not claim a PR is safe merely because Dependabot opened it. Safety requires PR metadata, checks, mergeability, and diff scope to line up.