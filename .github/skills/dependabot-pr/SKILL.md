---
name: dependabot-pr
description: "Manage one GitHub Dependabot pull request in any repository. Use when: auditing a specific Dependabot PR, deciding whether it is safe to merge, approving or merging it, rebasing or recreating it, or issuing an @dependabot command. Input: one PR URL or OWNER/REPO#NUMBER plus the requested action."
argument-hint: '<PR URL or OWNER/REPO#NUMBER> <action, e.g. audit, manage, merge-if-safe, rebase, recreate, ignore>'
---

# Dependabot Pull Request

Audit or manage exactly one Dependabot-authored GitHub pull request. The target
may belong to any GitHub repository.

## Atomic Scope

- Require one PR URL or an unambiguous `OWNER/REPO#NUMBER`.
- Operate only on that PR. Do not discover, list, inspect, comment on, approve,
  merge, or otherwise modify any other PR.
- If no target is supplied in an interactive session, ask for it. In an
  unattended session, stop with a target-validation error.
- Accept any GitHub owner and repository. Do not impose organization, product,
  programming-language, or local-workspace restrictions.
- Confirm the fetched owner, repository, and PR number match the supplied target.
- Confirm the author is `app/dependabot` or `dependabot[bot]`. If not, stop
  without taking a write action.

## Requested Action

Honor the user's requested action for the target PR:

- `audit`: inspect and report only.
- `manage` or `merge-if-safe`: audit, safely unblock when authorized, approve,
  and merge only if every safety rule passes.
- `approve`: approve only if every safety rule passes; do not merge.
- `merge`: merge only if every safety rule passes and required approval exists.
- `rebase`, `recreate`, `reopen`, `cancel merge`, `merge later`, or
  `squash-and-merge later`: issue the matching Dependabot command and verify its
  result.
- `close`, `ignore`, or `unignore`: explain the persistent effect and blast
  radius, then require explicit user confirmation before posting the command.

Do not perform writes when the request is only to inspect, explain, or assess
the PR.

## Fetch Complete Evidence

Use GitHub tools or `gh` to fetch the target PR's metadata, changed files,
commits, diff, reviews, unresolved review threads, and complete check rollup.
With `gh`:

```powershell
gh pr view PR_NUMBER --repo OWNER/REPO --json number,title,url,state,author,baseRefName,headRefName,headRefOid,isDraft,mergeStateStatus,reviewDecision,mergeable,changedFiles,additions,deletions,files,commits,statusCheckRollup
gh pr diff PR_NUMBER --repo OWNER/REPO
```

Never decide from the title, Dependabot body, or top-level green status alone.
Inspect the actual diff and the status of every check for the current head SHA.

## Safety Rules

A target PR is safe to approve or merge only when all applicable rules pass:

- It is open and not a draft.
- It is authored by Dependabot.
- Its commits and diff have clear provenance. Human-authored edits are understood
  and reviewed; they disqualify unattended recreation.
- `mergeable` is `MERGEABLE`.
- `mergeStateStatus` is `CLEAN`, or it is `BLOCKED` solely because required
  approval is missing while all other requirements pass.
- Every check run is completed with conclusion `SUCCESS`, `NEUTRAL`, or
  `SKIPPED`; every status context is `SUCCESS`. No required check is missing,
  pending, queued, stale, cancelled, timed out, action-required, or failing.
- There are no unresolved review threads requesting changes.
- The PR passes exactly one diff gate below.

### Standard Dependency Gate

- The diff changes only dependency manifests, lockfiles, checksums, vendored
  dependency metadata, or generated dependency files expected for that
  ecosystem.
- The update is low risk. Patch and minor updates are normally eligible.
- Major framework, runtime, build-tool, compiler, or other compatibility-sensitive
  updates require human review and are not automatically safe.
- Source, workflow, infrastructure, or unrelated configuration changes fail this
  gate.

### GitHub Actions-Only Gate

A GitHub Actions update may cross action major versions only when every
additional condition below passes:

- Every changed file is a `.yml` or `.yaml` file under `.github/workflows/`.
- Every added or removed patch line changes only a remote action `uses:`
  reference or its same-line version comment. Changes to triggers, permissions,
  jobs, steps, inputs, expressions, scripts, commands, environments, runner
  labels, or other workflow behavior fail this gate.
- Every changed action is from the GitHub-controlled `actions/*` or `github/*`
  namespace. Third-party actions, Docker actions, local actions, and reusable
  workflow references are not automatically safe.
- Old and new references use immutable full 40-character commit SHAs, not
  mutable tags or branches.
- Each new SHA resolves to the release tag named by its adjacent version comment.
  Verify tags through GitHub and peel annotated tags when necessary.
- Release and migration notes for every crossed major version show that all
  existing inputs and runtime requirements remain compatible.
- Paired actions, such as `actions/upload-artifact` and
  `actions/download-artifact`, use documented mutually compatible versions.
- Successful required checks exercise each changed build or test workflow.
  Issue-triage, scheduled, or manual-only workflows may lack direct PR execution
  only when the diff is reference-only and migration notes prove compatibility.

If any evidence is missing or unverifiable, the applicable gate fails.

## Branch Recovery and CI

- Branch recovery is allowed only for an open, non-draft, Dependabot-authored PR
  under an active management request. Before writing, prove that all branch
  commits are Dependabot-authored and that no human edits need preservation.
- For an eligible `DIRTY`, `BEHIND`, conflicted, or stale branch, request
  `@dependabot rebase` before making the final merge decision. Do this even when
  an independent safety blocker, such as a compatibility-sensitive major
  update, is already known and will still require human review.
- Record the old head SHA and count the rebase as successful only when the SHA
  changes and the PR remains open. Posting a command is not proof of success;
  inspect the changed PR state and Dependabot's response comment.
- After any head-SHA change, discard all previous diff and CI conclusions.
  Fetch the PR again, re-audit it, and evaluate checks for the new head before
  returning a final decision.
- If safe recovery eligibility cannot be proven, skip the rebase and report the
  exact provenance or human-edit concern.
- Recreation is more restrictive because it can discard branch changes. If
  rebase fails, use `@dependabot recreate` only when branch recovery is required
  for an otherwise automatically mergeable PR and no independent safety blocker
  would remain. Reconfirm that no human edits need preservation, request
  recreation once, and verify that the head SHA changes.
- Do not approve or merge while any check for the current head SHA is pending.
- If failed jobs may be transient and the user authorized active management,
  rerun failed jobs once, then wait for the rerun's terminal result.

## Approve and Merge

When the requested action authorizes approval and merge:

1. Approve only after the current head passes every safety rule.
2. Refresh the PR because approval may recalculate branch protection or trigger
   checks.
3. Wait for checks on the current head to become terminal.
4. Merge only when the refreshed PR is approved, mergeable, clean, and green.
5. Prefer the repository's established merge strategy; otherwise prefer squash.
6. Refresh once after a transient merge failure and retry once only if all
   safety conditions still pass.

Example `gh` fallback:

```powershell
gh pr review PR_NUMBER --repo OWNER/REPO --approve --body 'Approved: Dependabot dependency update with green checks.'
gh pr view PR_NUMBER --repo OWNER/REPO --json state,mergeStateStatus,mergeable,reviewDecision,statusCheckRollup
gh pr merge PR_NUMBER --repo OWNER/REPO --squash --delete-branch
```

## Dependabot Commands

Post commands only to the target PR:

| Command | Effect |
|---------|--------|
| `@dependabot rebase` | Rebase the PR onto its base branch. |
| `@dependabot recreate` | Recreate the PR and overwrite edits on its branch. |
| `@dependabot merge` | Merge after requirements pass. |
| `@dependabot squash and merge` | Squash-merge after requirements pass. |
| `@dependabot cancel merge` | Cancel a queued Dependabot merge. |
| `@dependabot reopen` | Reopen a closed Dependabot PR. |
| `@dependabot close` | Close the PR and prevent recreation of that exact update. |
| `@dependabot ignore this dependency` | Persistently ignore updates for the dependency. |
| `@dependabot ignore this major version` | Persistently ignore the current major line. |
| `@dependabot ignore this minor version` | Persistently ignore the current minor line. |
| `@dependabot ignore this patch version` | Persistently ignore the current patch line. |
| `@dependabot show DEPENDENCY_NAME ignore conditions` | Show stored ignore conditions. |

For grouped PRs, use dependency-specific forms:

```text
@dependabot ignore DEPENDENCY_NAME
@dependabot ignore DEPENDENCY_NAME major version
@dependabot ignore DEPENDENCY_NAME minor version
@dependabot ignore DEPENDENCY_NAME patch version
@dependabot unignore DEPENDENCY_NAME
@dependabot unignore DEPENDENCY_NAME IGNORE_CONDITION
@dependabot unignore *
```

Ignore and unignore commands may close or replace grouped PRs. Use the narrowest
command that matches explicit user intent.

## Final Report

Return a concise, self-contained report for this one PR:

- Repository, PR number, title, and clickable URL.
- Requested action and final outcome.
- Dependency or action version transitions and update type.
- Diff scope and safety gate applied.
- Final head SHA, merge state, review decision, and CI summary.
- Actions attempted, including rerun, rebase, recreate, approval, merge, or
  Dependabot commands, with their observed results.
- If not merged, the exact blocker and required next action.
- For a recovered PR that remains ineligible, distinguish the successful branch
  recovery from the remaining safety blocker. Do not tell a maintainer to rebase
  a branch that this run already rebased successfully.

Do not claim safety merely because Dependabot opened the PR. The current diff,
provenance, mergeability, reviews, and CI evidence must agree.
