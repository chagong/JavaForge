---
description: "Sync local repos with upstream remotes. Use when: syncing repos, pulling upstream changes, updating branches, fetching from origin."
agent: "agent"
tools: ["run_in_terminal"]
---

Sync the repositories in this workspace with their upstream remote branches.

The repos to sync are all top-level directories under the workspace root, plus the nested repo at `vscode-gradle/extension/build-server-for-gradle/`.

For each repo directory, do the following:

1. `cd` into the repo directory.
2. Run `git remote -v` to identify the upstream remote (the one pointing to the canonical/org repo, typically named `origin`).
3. Identify the default branch by running `git symbolic-ref refs/remotes/origin/HEAD` (fall back to `main` or `master` if that fails).
4. Fetch from the upstream remote: `git fetch origin`.
5. If the currently checked-out branch **is** the default branch, fast-forward it: `git merge --ff-only origin/<default-branch>`.
6. If the currently checked-out branch is **not** the default branch, stash any changes if needed, check out the default branch, fast-forward it (`git merge --ff-only origin/<default-branch>`), then check out the original branch again and restore the stash. Report both the default-branch update result and the fact the working branch was preserved.

Process repos one at a time. After finishing all repos, print a summary table showing:
- Repo name
- Branch before sync
- Upstream remote used
- Result (updated / already up-to-date / on feature branch / error)

If any repo has uncommitted changes, skip the merge for that repo and note it in the summary.
