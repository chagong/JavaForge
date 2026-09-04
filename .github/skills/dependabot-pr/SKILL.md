---
name: dependabot-pr
description: "Interact with one specified Dependabot pull request. Use when: fetching current PR state, issuing and verifying @dependabot commands, approving or merging after the caller has authorized the action, or checking the result of a write. This skill does not decide whether a PR is safe or mergeable."
argument-hint: '<PR URL or OWNER/REPO#NUMBER> <operation, e.g. inspect, rebase, recreate, approve, merge, ignore>'
---

# Dependabot Pull Request Interaction

Use this skill for the mechanics of reading or modifying exactly one
Dependabot-authored pull request.

## Responsibility Boundary

- This skill defines interaction procedures only.
- It does not define safety rules, evidence requirements, risk classifications,
  diff gates, CI policy, or merge eligibility.
- The caller must supply the target operation and decide whether any write is
  authorized.
- Never infer that a PR is safe because Dependabot opened it or because an
  operation succeeded.

## Validate the Target

1. Require one PR URL or an unambiguous `OWNER/REPO#NUMBER`.
2. Fetch the PR and confirm that the owner, repository, and number match the
   supplied target.
3. Confirm the author is `app/dependabot` or `dependabot[bot]`.
4. Operate only on that PR. Do not discover or touch another PR.
5. Stop without a write when the target or author cannot be verified.

## Read Current PR State

Use GitHub tools or `gh`. Return raw current state to the caller without making a
safety decision.

```powershell
gh pr view PR_NUMBER --repo OWNER/REPO --json number,title,url,state,author,baseRefName,headRefName,headRefOid,isDraft,mergeStateStatus,reviewDecision,mergeable,files,commits,statusCheckRollup
gh pr diff PR_NUMBER --repo OWNER/REPO
```

Record the current head SHA before a write. After any head-SHA change, fetch the
PR again instead of reusing earlier state.

## Dependabot Commands

Post commands only to the validated target PR.

| Command | Effect |
|---------|--------|
| `@dependabot rebase` | Rebase the PR onto its base branch. |
| `@dependabot recreate` | Recreate the PR and overwrite edits on its branch. |
| `@dependabot merge` | Merge after repository requirements pass. |
| `@dependabot squash and merge` | Squash-merge after repository requirements pass. |
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

`close`, `ignore`, and `unignore` have persistent effects and may close or
replace grouped PRs. Explain the effect and obtain explicit authorization before
posting them. Use the narrowest command that matches the request.

Example `gh` fallback:

```powershell
gh pr comment PR_NUMBER --repo OWNER/REPO --body '@dependabot rebase'
```

## Verify Dependabot Commands

Posting a command is not proof that it worked.

1. Record the pre-command head SHA and PR state.
2. Post the exact command once.
3. Inspect Dependabot's response comment.
4. Verify the expected state transition:
   - `rebase` or `recreate`: the head SHA changes and the PR remains open.
   - `reopen`: the PR becomes open.
   - `close`: the PR becomes closed.
   - merge commands: `mergedAt` becomes non-null.
   - ignore or unignore: Dependabot confirms the requested condition.
5. Report the observed response, old and new head SHAs, and final PR state to
   the caller.

If the head SHA changes, discard earlier diff and check results. The caller must
request fresh evidence before making another decision.

## Direct Approval and Merge

Perform direct GitHub writes only when the caller explicitly authorizes the
specific action. This section provides execution mechanics, not approval policy.

```powershell
gh pr review PR_NUMBER --repo OWNER/REPO --approve --body "Approved."
gh pr merge PR_NUMBER --repo OWNER/REPO --squash --delete-branch
```

After approval, fetch the PR and report the current review decision. After a
merge attempt, fetch `state`, `mergedAt`, `mergeable`, and `mergeStateStatus`.
Retry only when the caller explicitly requests it.

## Return the Operation Result

Return:

- Repository, PR number, title, and URL.
- Requested operation.
- Whether a write was attempted.
- Dependabot or GitHub response.
- Old and new head SHAs when relevant.
- Final PR state.
- Any interaction error or missing authorization.

Do not include a merge-safety conclusion unless the caller supplied it.
