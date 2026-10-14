---
description: "Refresh backing repos from upstream without disturbing task worktrees. Use when: syncing repos, pulling upstream changes, preparing task worktrees, updating default branches."
agent: "agent"
tools: [vscode, execute, read, agent, browser, vscodeGeneral/rename, vscodeGeneral/usages, vscodeNotebooks/createJupyterNotebook, vscodeNotebooks/editNotebook, edit, search, web, 'github/*', todo]
---

Refresh the repositories in this workspace from their original upstream remotes, preserving existing task worktrees and local changes.

Use the canonical repository list in `.github/copilot-instructions.md`. Sync only the requested repositories when specified; otherwise process the locally available backing clones in that list, including `repos/vscode-gradle/extension/build-server-for-gradle/` when present. An explicitly supplied backing clone outside `repos/` is also supported. Do not clone missing repositories merely to sync them.

For each backing repository, do the following:

1. Verify the repository path and inspect `git worktree list --porcelain`. Worktrees share Git refs; process each backing repository once, not every task worktree. If the supplied path is a task worktree, locate its backing checkout before considering a merge.
2. Run `git remote -v` to identify the original upstream remote by matching the canonical/org repository URL. A fork's `origin` is not necessarily the original upstream. If no remote matches, report the blocker rather than fetching or merging from an unrelated repository.
3. Identify the upstream default branch with `git ls-remote --symref <upstream> HEAD`. If the query fails or does not identify a branch, report the error instead of guessing `main` or `master`.
4. Fetch from that remote: `git fetch <upstream>`. If fetching fails, report the error and do not merge.
5. If the backing checkout **is** on the default branch and has no uncommitted tracked changes, fast-forward it with `git merge --ff-only <upstream>/<default-branch>`. If it diverges or untracked files block the merge, report the blocker; do not reset or remove files.
6. If the backing checkout is dirty, on a feature branch, or detached, leave it untouched and report **fetched only**, with the reason. The refreshed `<upstream>/<default-branch>` ref can be used to create a new task worktree without switching the backing checkout.

Never discard changes, switch existing branches, rebase task branches, force-update refs, or remove worktrees as part of syncing. Do not merge into active task worktrees.

Process repos one at a time. After finishing all repos, print a summary table showing:
- Repo name
- Backing checkout path
- Branch before sync
- Upstream remote used
- Result (updated / already up-to-date / fetched only with reason / not available locally / error)

Uncommitted **tracked** changes (modified or staged files) prevent a merge, not a fetch. **Untracked files** (e.g., nested git repos appearing as `??` in `git status`) should **not** cause an automatic skip — use `git status --porcelain` filtered to exclude lines starting with `??`, but preserve untracked files if Git reports that they would be overwritten.
