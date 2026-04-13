---
description: "Use when: bumping extension versions, preparing releases, creating version bump PRs, updating changelogs for any Java extension repo in this workspace."
---

# Version Bump Procedure

## Version Rule

- **Minor version bump** (e.g. 0.44.0 → 0.45.0): when there are **feature-level** changes (new user-facing capabilities)
- **Patch version bump** (e.g. 0.45.0 → 0.45.1): when there are only **bug fixes**, **performance improvements**, or other non-feature changes

## Files to Update

For each extension, update **all three** files:

1. **`package.json`** — bump `"version"` field
2. **`package-lock.json`** — run `npm install --package-lock-only` to sync
3. **`CHANGELOG.md`** — add new version entry at the top

Note: `vscode-gradle` has its `package.json` and `package-lock.json` under `extension/`, not the repo root.

## Changelog Rules

- Only include **user-facing changes**: features, bug fixes, performance improvements
- **Exclude**: CI changes, dependency bumps (dependabot), test infrastructure, internal refactors
- Include changes from **sub-module repos** in the parent extension's changelog:
  - `vscode-gradle` includes changes from `microsoft/build-server-for-gradle`
  - `vscode-java-debug` includes changes from `microsoft/java-debug`
- Follow each repo's existing changelog format (see below)

## Changelog Formats by Repo

| Repo | Format |
|------|--------|
| `vscode-gradle` | `## {version}` → `## What's Changed` → `* type - description in URL` |
| `vscode-java-dependency` | `## {version}` → `- type - description in URL` |
| `vscode-java-debug` | `## {version} - {YYYY-MM-DD}` → `### Added/Fixed/Changed` → `- description. [ref](URL).` |
| `vscode-java-test` | `## {version}` → `## What's Changed` → `* type - description in URL` |
| `vscode-maven` | `## {version}` → `### Added/Fixed/Changed` → `- description [#N](URL)` |

## PR Procedure

1. **Find the last stable release date** for each extension (and sub-modules) using GitHub releases
2. **Search merged PRs** since that date
3. **Filter** to user-facing changes only
4. **Determine version bump** (minor vs patch) based on whether features are present
5. **Create a branch** named `bump-version-{new-version}` from the default branch
   - Default branches: `develop` for vscode-gradle, `main` for all others
6. **Update** `package.json`, run `npm install --package-lock-only`, update `CHANGELOG.md`
7. **Commit** with message `bump version to {new-version}`
8. **Push** and **create PR** with changelog summary in the PR body

## Sub-Module Repos

| Parent Extension | Sub-Module Repo | What to Include |
|-----------------|----------------|-----------------|
| `vscode-gradle` | `microsoft/build-server-for-gradle` | BSP server changes |
| `vscode-java-debug` | `microsoft/java-debug` | Debug server changes |
