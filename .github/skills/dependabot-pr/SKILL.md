---
name: dependabot-pr
description: "Send and verify @dependabot comment commands on one specified Dependabot pull request: rebase, recreate, merge, cancel merge, reopen, close, ignore, unignore, or show ignore conditions. This skill does not provide general GitHub PR operations or decide whether a PR is safe to merge."
argument-hint: '<PR URL or OWNER/REPO#NUMBER> <@dependabot command>'
---

# Dependabot Comment Commands

Use this skill only to send `@dependabot` commands and verify Dependabot's
response on exactly one Dependabot-authored pull request.

## Responsibility Boundary

- This skill defines Dependabot command syntax, posting, and verification only.
- General GitHub PR management, dependency audits, CI policy, and merge
  eligibility belong to the caller.
- The caller must supply the exact command and decide whether the write is
  authorized.
- Never infer that a PR is safe because Dependabot opened it or because an
  issued command succeeded.

## Validate the Target

Read PR metadata only as needed to validate the command target and observe its
effect.

1. Require one PR URL or an unambiguous `OWNER/REPO#NUMBER`.
2. Fetch the PR and confirm that the owner, repository, and number match the
   supplied target.
3. Confirm the author is `app/dependabot` or `dependabot[bot]`.
4. Operate only on that PR. Do not discover or touch another PR.
5. Stop without a write when the target or author cannot be verified.

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

## Send and Verify Dependabot Commands

Posting a command is not proof that it worked.

1. Record the pre-command head SHA and PR state.
2. Post the exact command once.
3. Inspect Dependabot's response comment.
4. Verify the expected state transition:
   - `rebase` or `recreate`: the head SHA changes and the PR remains open.
   - `reopen`: the PR becomes open.
   - `close`: the PR becomes closed.
   - merge commands: `mergedAt` becomes non-null.
   - `cancel merge`: Dependabot confirms cancellation of the queued merge.
   - ignore or unignore: Dependabot confirms the requested condition.
   - show ignore conditions: Dependabot returns the stored conditions; no state
     change is expected.
5. Report the target, exact command, whether it was posted, observed bot
   response, old and new head SHAs when relevant, final PR state, and any error
   or missing authorization.

Distinguish a pending or queued command from a completed operation. Report any
head-SHA change so the caller can refresh its evidence.
