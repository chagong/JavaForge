---
name: dependabot-pr
description: "Manage one GitHub Dependabot pull request in any repository. Use when: auditing a specific Dependabot PR, removing an unused direct dependency, fixing compatibility issues from a major update, deciding whether it is safe to merge, approving or merging it, rebasing or recreating it, or issuing an @dependabot command. Input: one PR URL or OWNER/REPO#NUMBER plus the requested action."
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
- `manage` or `merge-if-safe`: audit, safely unblock when authorized, remediate
  compatibility-sensitive major updates when eligible, remove a direct
  dependency when it is proven unused, approve, and merge only if every safety
  rule passes.
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

## Dependency Necessity Check

Before retaining or upgrading any direct dependency, prove that the repository
still needs it. Repeat this check after every compatibility refactor because a
migration can remove the dependency's final usage.

- Classify the dependency as runtime, development, optional, peer, plugin,
  processor, build-tool, or generated-code input.
- Search tracked source, tests, scripts, build files, workflow files, bundler
  configuration, package metadata, extension/plugin declarations, command
  strings, dynamic imports, reflection/service-loader configuration, and
  generated-code inputs. Exclude lockfiles, vendored dependency directories, and
  the dependency declaration itself from positive usage evidence.
- Use ecosystem dependency analysis where available (`npm explain`/`npm ls`,
  `pnpm why`, `yarn why`, Maven dependency analysis, Gradle dependency reports,
  or the equivalent). A package remaining transitively installed does not prove
  that its direct declaration is needed.
- Map every imported or invoked API to the dependency that actually provides it.
  Account for aliases, subpath imports, type-only imports, CLI binaries, loaders,
  test adapters, and configuration-only usage. A plain text search alone is not
  enough to prove absence.
- If the only usages are private helpers that the remediation replaces with
  platform APIs, local code, or another already-declared package, rerun the
  complete search after that replacement.
- When no required runtime, build, test, type, or configuration role remains,
  prefer removing the direct dependency over upgrading it. Do not keep a package
  merely because the original PR was opened as a version bump.
- Do not reimplement substantial library behavior merely to make a dependency
  removable. Prefer removal only when the remaining use is obsolete, private,
  trivial to replace with platform APIs or already-declared packages, and covered
  by focused tests.
- Remove it with the ecosystem package manager so manifests and lockfiles stay
  synchronized. Also remove obsolete overrides, externals, allowlists, notices,
  license entries, and packaging metadata directly tied to that dependency.
- When converting a bump PR into a removal, first restore the affected manifests
  and lockfiles from the PR base, preserve the focused source/test remediation,
  and then run the ecosystem removal command. This prevents bump-only transitive
  resolution churn from surviving the removal.
- Verify the direct declaration is gone and explain whether the package also
  disappeared from the resolved tree or remains only as a transitive dependency.
- Validate clean installation, compile/build, packaging, and relevant tests after
  removal. For runtime dependencies, confirm the packaged artifact no longer
  contains or requires the package.
- When removal is proven, update the target PR title and body to describe removal
  rather than a bump. Do not post an ignore command; removing the manifest entry
  prevents Dependabot from proposing that direct update again.
- If usage is dynamic or otherwise cannot be proven absent, do not remove the
  dependency. Continue with a justified upgrade or report the uncertainty as a
  blocker.

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
- The Dependency Necessity Check passes and the PR passes exactly one diff gate
  below.

### Standard Dependency Gate

- The diff changes only dependency manifests, lockfiles, checksums, vendored
  dependency metadata, or generated dependency files expected for that
  ecosystem.
- The update is low risk. Patch and minor updates are normally eligible.
- A manifest-and-lockfile-only removal of a proven-unused direct dependency is
  normally eligible.
- Major framework, runtime, build-tool, compiler, or other compatibility-sensitive
  updates must use the Major Upgrade Remediation Gate. Do not stop merely because
  an update crosses a major version.
- Source, workflow, infrastructure, or unrelated configuration changes fail this
  gate.

### Major Upgrade Remediation Gate

A compatibility-sensitive major update may be fixed and merged autonomously
under `manage` or `merge-if-safe` only when all conditions below pass:

- At entry, the PR changes only dependency manifests, lockfiles, checksums,
  vendored dependency metadata, or expected generated dependency files.
- The head branch belongs to the base repository, every existing commit is
  Dependabot-authored, and no human edits need preservation. Remediate the target
  PR branch in place; do not create, inspect, or modify another PR.
- Fetch release notes, migration guides, changelogs, package metadata, runtime
  engine constraints, peer dependencies, and the complete transitive lockfile
  change. Missing or unverifiable breaking-change evidence fails this gate.
- Search every usage and configuration surface affected by the dependency,
  including imports, generated assets, build scripts, runtime loaders, test
  discovery, workflows, and packaging. Read repository instructions and CI
  workflows before editing.
- Reproduce current CI or build failures and distinguish dependency
  incompatibilities from transient infrastructure failures.
- Before implementing an upgrade migration, decide whether the dependency should
  still exist. If the migration removes its final required usage, remove the
  dependency and do not retain the new version.
- Implement only the compatibility changes required by the update. Source,
  configuration, workflow, and test changes are allowed under this gate when
  directly caused by the major upgrade; unrelated cleanup is not.
- Use the repository's package manager or build tool to update manifests and
  generated lockfiles. Do not hand-edit generated dependency metadata.
- Add focused regression coverage for each migrated API or behavior. Validate
  clean installation, lint/type-check, compile/build, packaging, and the smallest
  relevant test suite. Run integration or end-to-end tests for runtime or
  user-facing behavior; use a browser smoke test for browser assets when no
  existing UI test covers them.
- When runtime, compiler, package-manager, or editor engine requirements change,
  test the minimum supported runtime directly or align the declared minimum and
  all CI/release pipelines. Do not infer runtime compatibility from a successful
  bundle alone.
- Preserve failures explicitly. Do not add silent success fallbacks. If an
  external inspection can fail, surface the error and represent an indeterminate
  state rather than incorrectly reporting success or failure.
- Review the final diff for scope, type safety, generated-file consistency, and
  minimum-runtime behavior before pushing.
- Push only after local validation passes. Use a conventional commit with any
  repository-required sign-off or trailers and a normal, non-force push to the
  target PR head branch. Agent-authored commits created during this run have
  understood provenance and are eligible; human commits that predate the run
  are not.
- After every push, discard prior CI conclusions, fetch the new head, inspect the
  complete diff, and drive CI to a terminal state. Diagnose deterministic
  failures from logs, apply focused fixes, and repeat while the execution budget
  permits.
- For agent-authored remediation or removal commits, request an independent code
  review on the final head when the repository provides one. Wait for its bounded
  result before approval; re-enter remediation for actionable findings.
- The final head must have green required checks, no unresolved review threads,
  and no unaddressed breaking-change evidence. Otherwise leave the PR open and
  report the exact remaining blocker and failed validation.

Related major updates from separate PRs may be consolidated only when the user
explicitly requests a multi-PR workflow. This one-PR skill must never discover
or modify sibling PRs.

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

- In an unattended one-shot invocation, never leave a decision-critical shell
  command running in the background. Poll with individual foreground reads or
  bounded loops that complete within 4 minutes. If a tool backgrounds a command,
  consume its terminal result with the matching read tool before ending the turn;
  a completion notification cannot start another one-shot model turn.
- Branch recovery is allowed only for an open, non-draft, Dependabot-authored PR
  under an active management request. Before writing, prove that all branch
  commits are Dependabot-authored and that no human edits need preservation.
- For an eligible `DIRTY`, `BEHIND`, conflicted, or stale branch, request
  `@dependabot rebase` before making the final merge decision. Do this even when
  an independent safety blocker is already known.
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
- Perform Dependabot rebase or recreation before major-upgrade remediation.
  After an agent-authored compatibility commit is pushed, never recreate the PR
  or use another operation that could discard that commit.
- Do not approve or merge while any check for the current head SHA is pending.
- If failed jobs may be transient and the user authorized active management,
  rerun failed jobs once, then wait for the rerun's terminal result.

## Approve and Merge

When the requested action authorizes approval and merge:

1. Repeat the Dependency Necessity Check on the final head. Approve only after
   that check and every safety rule pass.
2. If an independent review was requested for agent-authored changes, wait for it
   to complete and inspect every finding before approval.
3. Refresh the PR because approval may recalculate branch protection or trigger
   checks.
4. Wait for checks on the current head to become terminal.
5. If the refreshed review decision remains `REVIEW_REQUIRED` because the
   current actor cannot satisfy code-owner or required-review policy, stop with
   that terminal blocker. Do not poll waiting for an external human.
6. Merge only when the refreshed PR is approved, mergeable, clean, and green.
7. Prefer the repository's established merge strategy; otherwise prefer squash.
8. Refresh once after a transient merge failure and retry once only if all
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
- For removal, report the transition as `OLD_VERSION -> removed`, why no required
  usage remains, and whether any transitive copy remains.
- Diff scope and safety gate applied.
- Final head SHA, merge state, review decision, and CI summary.
- Actions attempted, including rerun, rebase, recreate, approval, merge,
  Dependabot commands, compatibility edits, local validation, commits, and
  pushes, with their observed results.
- If not merged, the exact blocker and required next action.
- For a recovered PR that remains ineligible, distinguish the successful branch
  recovery from the remaining safety blocker. Do not tell a maintainer to rebase
  a branch that this run already rebased successfully.

Do not claim safety merely because Dependabot opened the PR. The current diff,
provenance, mergeability, reviews, and CI evidence must agree.
