---
name: dependabot-pr
description: "Interact with one specified Dependabot pull request. Use when: fetching current PR state, updating a branch, issuing and verifying @dependabot commands, upserting a management-result comment, approving or merging after the caller has authorized the action, or checking the result of a write. This skill does not decide whether a PR is safe or mergeable."
argument-hint: '<PR URL or OWNER/REPO#NUMBER> <operation, e.g. inspect, update-branch, rebase, comment-result, approve, merge>'
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
gh pr view PR_NUMBER --repo OWNER/REPO --json number,title,url,state,author,baseRefName,baseRefOid,headRefName,headRefOid,headRepository,headRepositoryOwner,isCrossRepository,isDraft,mergeStateStatus,reviewDecision,mergeable,files,commits,statusCheckRollup
gh pr diff PR_NUMBER --repo OWNER/REPO
```

Record the current head SHA before a write. After any head-SHA change, fetch the
PR again instead of reusing earlier state.

## Update the PR Branch

Use GitHub's update-branch operation only when the caller has authorized a
conflict-free base merge that must preserve existing head commits.

```powershell
gh api --method PUT repos/OWNER/REPO/pulls/PR_NUMBER/update-branch `
  -f expected_head_sha=RECORDED_HEAD_SHA
```

Verify that:

- GitHub accepted the expected head SHA.
- The head SHA changed and the PR remains open.
- Every commit the caller required preserving remains an ancestor of the new
  head.
- The resulting merge commit's first parent matches the recorded old head.
- The actual base parent equals or descends from the audited base SHA and belongs
  to the target's current base-branch history.

Return the old head SHA, audited base SHA, actual applied-base parent SHA, new
merge SHA, and preserved ancestor SHA. An expected-SHA mismatch, conflict
response, unchanged head, invalid base ancestry, parent mismatch, or lost
remediation ancestry is a failed operation. Do not retry with a different SHA
unless the caller reauthorizes from freshly audited state.

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

## Upsert a Management Result Comment

When the caller authorizes a final result comment:

1. Include the marker `<!-- dependabot-pr-manager-result -->`.
2. Include one valid hidden `dependabot-pr-manager-provenance` JSON line.
3. Include one valid hidden `dependabot-pr-manager-state` JSON line and verify
   repository, PR number, head SHA, and decision against fresh GitHub state.
   Reject target identity or author mismatches even for incomplete fallback
   reports; a result marker does not establish a valid target.
4. Find the current authenticated actor's existing issue comment containing that
   unique marker.
5. Before replacement, prove the new ledger contains every verified remediation
   and update-branch entry in the existing ledger. Missing entries fail closed;
   never overwrite the prior comment.
6. Update the existing comment through
   `PATCH /repos/OWNER/REPO/issues/comments/COMMENT_ID`; otherwise create it
   through `POST /repos/OWNER/REPO/issues/PR_NUMBER/comments`.
7. Verify and return the comment URL and body.

Never post more than one marked result comment per target PR. Do not post in
dry-run mode or when target validation failed. A malformed or incomplete manager
response must not replace an existing marked comment.

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
