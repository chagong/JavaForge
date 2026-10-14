---
description: "Use when: creating or updating pull requests, pushing PR commits, monitoring PR CI status. Governs the post-PR workflow for CI polling, failure remediation, and review assignment."
---

# PR Workflow

Before using the app's PR creation tool, ensure the session's repository matches
the target repository. For sub-repository work, use a session belonging to that
repository and its task worktree (or an explicitly requested in-place checkout),
not the JavaForge session. Follow the workspace selection rules in
`.github/copilot-instructions.md`; changing the shell directory does not retarget
the session-scoped PR tool.
Push the session branch before calling the PR creation tool; an unpublished head
can cause GitHub to reject creation with HTTP 422.

For `gh pr checkout`, first change the shell directory to the target task worktree.
`--repo` selects the remote PR but does not change which local repository is
modified. Confirm the worktree's repository and branch immediately after checkout.

After creating or updating a pull request, follow this post-PR workflow.

## 1. Poll CI Status

- After the PR is created (or new commits are pushed), poll the CI workflow status every **5 minutes** until all PR CI workflows reach a terminal state (success or failure).
- Use the GitHub API to check the status of all workflow runs associated with the PR's head SHA.
- Do not stop polling until every required workflow has completed.
- An external pipeline trigger suggested by a bot comment is not necessarily
  required. Check both classic branch protection and active branch rulesets
  before treating an untriggered pipeline as a readiness blocker; report an
  optional trigger separately.

## 2. Handle CI Failures

- If **any** CI workflow fails, retrieve the CI job logs using the `get-ci-logs` skill.
- Classify each failure as caused by the PR, flaky/transient, unrelated, or
  indeterminate. Compare the merge base or a current default-branch run when
  needed to establish causality.
- Fix, commit, and push only failures caused by the PR. Do not change source,
  tests, snapshots, timeouts, or CI configuration for flaky, unrelated, or
  indeterminate failures; report those failures and their evidence instead.
- After pushing the fix, restart polling from step 1.

## 3. Assign Review on Success

- Once **all** CI workflows pass, assign `@copilot` as a reviewer on the pull request for code review.
- After CI reaches a terminal state and before reporting the PR ready or drafting a review-thread reply, refresh the PR review comments and reviews. Address any newly added unresolved feedback first.
