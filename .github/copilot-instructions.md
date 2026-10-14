# Copilot Instructions — Java Extensions for VS Code

This workspace is a development environment for coding agents (GitHub Copilot, Claude Code, etc.) to work on **Java tooling for VS Code**. It may contain any subset of the repositories listed below — prefer isolated task worktrees backed by reusable clones under `repos/`, and clone only when no suitable backing repository is available.

For detailed architecture, internal APIs, module maps, and communication patterns, see [Java-Tooling-Architecture.md](../javatooling-architecture.md).

---

## Pre-Work Repository Sync

Before starting a new issue investigation, bug fix, feature implementation, or other source-level task, fetch the relevant repository's original upstream and base the new task worktree on its current default branch. Use the `/sync-repos` prompt to refresh the backing repository without disturbing existing work. A dirty or feature-branch backing checkout can remain unchanged; the fetched upstream ref is sufficient to create a new worktree.

When continuing an existing task or PR, preserve its worktree and branch. Do not switch, reset, or rebase it merely to satisfy the pre-work sync requirement.

---

## Scratch Folder

The `scratch/` directory is a gitignored workspace for task worktrees and temporary files — extracted JARs, patched binaries, build artifacts for local testing, etc. Always use `scratch/` instead of creating ad-hoc folders in the workspace root. Contents are excluded from JavaForge version control; only `.gitkeep` is tracked.

Task worktrees are not disposable scratch artifacts: they may contain uncommitted changes or unpublished commits. Do not delete them during temporary-file cleanup.

---

## Repository Folder

The `repos/` directory holds reusable backing clones of Java tooling repositories and upstream dependencies, not the default editing workspace. Keep the folder itself in the workspace with `repos/.gitkeep`, but keep cloned repositories ignored by version control. Do not clone Java tooling repositories into the workspace root.

### Preferred Task Worktrees

1. Reuse an existing worktree when it belongs to the requested task, including a user-provided or app-managed worktree. Otherwise, locate the backing clone at the canonical `repos/<repo>/` path or an explicitly supplied local path. Verify that its original upstream matches the repository in the table below before reusing it. Clone into the canonical path only when no suitable backing clone exists; never overwrite an unrelated repository at that path.
2. Refresh the original upstream as described in "Pre-Work Repository Sync". Identify its actual default branch from remote metadata; do not assume `origin` is the original upstream or that the branch is `main`.
3. Inspect `git worktree list --porcelain` in the backing repository. For a new task, create a uniquely named branch and worktree at `scratch\worktrees\<repo>\<task>`, using `git worktree add -b <task-branch> <absolute-task-path> <upstream>/<default-branch>`. Resolve the task path from the JavaForge root before running Git from another directory. For an existing PR, use its head branch or exact recorded SHA instead of the default branch. Never use `-B` or force options to replace another task's branch or worktree.
4. Run source searches, edits, dependency installation, builds, tests, and task Git commands in the selected worktree. The `repos/...` paths in the tables below identify backing repositories; substitute the task worktree root while preserving repository-relative paths.
5. Handle nested repositories separately. A `vscode-gradle` worktree does not automatically include the independent Build Server for Gradle repository. When needed, create or reuse a worktree of that repository at `<gradle-task-worktree>\extension\build-server-for-gradle`, backed by its own clone.

Respect explicit in-place requests and host/session restrictions on creating branches or worktrees. This preference does not authorize switching the JavaForge checkout or discarding existing work. If a worktree cannot be created within those restrictions, ask before falling back to editing the backing clone.

Before using GitHub APIs for source lookup, inspect the selected task worktree, then the canonical backing path under `repos/<repo>/`. If a recursive search reports no match, check the mapped backing path and, when it exists, `git worktree list --porcelain` before concluding that the source is unavailable.

---

## Repositories in This Workspace

| Folder | Role | Repository |
|--------|------|------------|
| `repos/vscode-java/` | Java Language Support — LSP client (TypeScript), central hub extension | https://github.com/redhat-developer/vscode-java |
| `repos/eclipse.jdt.ls/` | Eclipse JDT Language Server — LSP server powering all Java language features (Java) | https://github.com/eclipse-jdtls/eclipse.jdt.ls |
| `repos/eclipse.jdt.core/` | Eclipse JDT Core — compiler (ECJ), Java model, AST, search, formatter (Java) | https://github.com/eclipse-jdt/eclipse.jdt.core |
| `repos/vscode-java-debug/` | Debugger for Java — DAP client extension (TypeScript) | https://github.com/microsoft/vscode-java-debug |
| `repos/java-debug/` | Java Debug Server — DAP server over JDI (Java) | https://github.com/microsoft/java-debug |
| `repos/vscode-java-test/` | Test Runner for Java — VS Code Testing API integration (TypeScript + Java) | https://github.com/microsoft/vscode-java-test |
| `repos/vscode-gradle/` | Gradle for Java — project management, task runner, `.gradle` editing (TypeScript + Java) | https://github.com/microsoft/vscode-gradle |
| `repos/vscode-gradle/extension/build-server-for-gradle/` | Build Server for Gradle — BSP server, sub-project of vscode-gradle (Java) | https://github.com/microsoft/build-server-for-gradle |
| `repos/vscode-java-dependency/` | Project Manager for Java — project explorer, library management, JAR export (TypeScript + Java) | https://github.com/microsoft/vscode-java-dependency |
| `repos/vscode-maven/` | Maven for Java — project explorer, POM editing, lifecycle execution (TypeScript + Java) | https://github.com/microsoft/vscode-maven |
| `repos/vscode-java-pack/` | Extension Pack for Java — bundles all Java extensions, walkthrough, tips (TypeScript) | https://github.com/microsoft/vscode-java-pack |
| `repos/vscode-spring-initializr/` | Spring Initializr Java Support — Spring Boot project scaffolding, dependency management (TypeScript) | https://github.com/microsoft/vscode-spring-initializr |
| `repos/vscode-spring-boot-dashboard/` | Spring Boot Dashboard — app lifecycle management, beans/endpoints explorer (TypeScript + Java) | https://github.com/microsoft/vscode-spring-boot-dashboard |

---

## VS Code Extensions ↔ Repository Mapping

| Extension ID | Extension Name | VS Code Extension Repo | Backend/Server Repo |
|-------------|---------------|----------------------|---------------------|
| `redhat.java` | Language Support for Java | `repos/vscode-java/` | `repos/eclipse.jdt.ls/` + `repos/eclipse.jdt.core/` |
| `vscjava.vscode-java-debug` | Debugger for Java | `repos/vscode-java-debug/` | `repos/java-debug/` |
| `vscjava.vscode-java-test` | Test Runner for Java | `repos/vscode-java-test/` | (Java plugin in same repo) |
| `vscjava.vscode-gradle` | Gradle for Java | `repos/vscode-gradle/` | (Java servers in same repo) |
| `vscjava.vscode-java-dependency` | Project Manager for Java | `repos/vscode-java-dependency/` | (Java plugin in same repo) |
| `vscjava.vscode-maven` | Maven for Java | `repos/vscode-maven/` | (Java plugin in same repo) |
| `vscjava.vscode-java-pack` | Extension Pack for Java | `repos/vscode-java-pack/` | — (pack only, no backend) |
| `vscjava.vscode-spring-initializr` | Spring Initializr Java Support | `repos/vscode-spring-initializr/` | — |
| `vscjava.vscode-spring-boot-dashboard` | Spring Boot Dashboard | `repos/vscode-spring-boot-dashboard/` | (Java plugin in same repo) |

### Extension Dependency Chain

- `vscode-java-test` → depends on `redhat.java` + `vscjava.vscode-java-debug`
- `vscode-java-debug` → depends on `redhat.java`
- `vscode-gradle`, `vscode-java-dependency`, `vscode-maven` → runtime integration with `redhat.java` (no hard dependency)
- `vscode-spring-boot-dashboard` → depends on `vmware.vscode-spring-boot` + `redhat.java` + `vscjava.vscode-java-debug`
- `vscode-spring-initializr` → standalone (no hard dependency)
- `vscode-java-pack` → extension pack that bundles all of the above; also contributes walkthroughs and Getting Started content
- `redhat.java` → embeds `eclipse.jdt.ls` which depends on `eclipse.jdt.core`

---

## Constraints for Resolving Issues and Feature Requests

When working on bug fixes or feature requests for any repo in this workspace, all changes **must** satisfy the following requirements before a PR is considered ready:

### 1. Unit Tests Must Pass

Every repo has unit tests that must pass locally before submitting a PR.

| Repo Path | Test Command | Build System | Notes |
|------|-------------|-------------|-------|
| `repos/vscode-java/` | `npm test` | Mocha | Requires X11 on Linux (`xvfb-run`) |
| `repos/eclipse.jdt.ls/` | `./mvnw clean verify` | JUnit (OSGi plugin tests) | Requires JDK 21+ |
| `repos/eclipse.jdt.core/` | `./mvnw clean verify` | JUnit (OSGi plugin tests) | Multi-compliance: Java 8, 11, 17, 21, 25, 26 |
| `repos/vscode-java-debug/` | `npm test` | Mocha | — |
| `repos/java-debug/` | `./mvnw clean verify` | JUnit 4 + EasyMock | Requires JDK 21+ |
| `repos/vscode-java-test/` | `npm run build-plugin && npm test` | Mocha + Maven | Build Java plugin first |
| `repos/vscode-gradle/` | `./gradlew build testVsCode` | Mocha + JUnit + Gradle | Build JARs in a separate invocation first: `cd extension && ../gradlew buildJars` |
| `repos/vscode-java-dependency/` | `npm run build-server && npm test` | Mocha + Maven | Build Java plugin first |
| `repos/vscode-maven/` | `npm run build-plugin && npm test` | Mocha + Maven | Build Java plugin first |
| `repos/vscode-spring-initializr/` | `npm test` | Mocha | — |
| `repos/vscode-spring-boot-dashboard/` | `npm test` | Mocha | Build Java plugin first: `npm run prepublish` |

On Windows, `NoDefaultCurrentDirectoryInExePath=1` can prevent child processes
from finding bare `gradlew` or `mvnw` commands despite the wrappers being present.
Add the actual wrapper directories to the process-local `PATH` (for example,
`extension\build-server-for-gradle` and `extension\jdtls.ext` in `vscode-gradle`).
Do not unset the search-path protection or change global environment settings.

For extension-host probes outside the target extension directory, load `vscode`
via `require("module").createRequire(targetCompiledModulePath)("vscode")` before
stubbing APIs. VS Code returns extension-scoped API objects; a direct import from
an external probe can stub a different object from the code under test.

Remote-workspace probes must model the extension's execution host. Workspace
extensions normally receive `file` URIs after VS Code converts incoming
`vscode-remote` URIs; do not inject UI-side URIs into that host model.

For multi-root configuration tests, open a `.code-workspace` file when starting
the test host; converting a single-folder host in a test hook can leave
`updateWorkspaceFolders` waiting without a workspace-change event.

Verify extension-host error logging through captured host output; overriding a
probe's `console.error` may not intercept another module's console object.

For launch-candidate merges, cover all-test discoveries with valid, absent, and
rejected custom launchers. Mixed production/test fixtures do not exercise the
all-test fallback.

### 2. UI Tests Must Pass (Where Applicable)

Some repos have dedicated UI test workflows that validate end-to-end behavior:

| Repo Path | UI Test Workflow | Platforms |
|------|-----------------|-----------|
| `repos/vscode-java-dependency/` | `windowsUI.yml`, `linuxUI.yml` | Windows, Linux |

### 3. PR CI Checks Must Pass

Every repo runs CI on pull requests. A PR cannot be merged until all CI checks are green. Always check the CI status on GitHub after pushing commits, and investigate any failures before requesting reviews.

| Repo Path | CI Workflows | Platforms |
|------|-------------|-----------|
| `repos/vscode-java/` | `pr-verify.yml` — build, lint (`eslint`), test, package | macOS, Linux |
| `repos/eclipse.jdt.core/` | `ci.yml` — full verify; `pr-checks.yml`; `codeql.yml` | Linux, Windows, macOS |
| `repos/eclipse.jdt.ls/` | `licensecheck.yml` — license vetting; `codeql-analysis.yml` | Linux |
| `repos/vscode-java-debug/` | `build.yml` — lint (`tslint`), build, test, package | Linux |
| `repos/java-debug/` | `build.yml` — verify + checkstyle | Linux, Windows |
| `repos/vscode-java-test/` | `build.yml` — build-plugin, lint, compile, test, package | Linux |
| `repos/vscode-gradle/` | `main.yml` — build, lint, test, SonarQube analysis | Ubuntu |
| `repos/vscode-java-dependency/` | `linux.yml`, `windows.yml`, `macOS.yml`, `linuxUI.yml`, `windowsUI.yml` | Linux, Windows, macOS |
| `repos/vscode-maven/` | `linux.yml`, `windows.yml`, `macOS.yml` | Linux, Windows, macOS |
| `repos/vscode-spring-initializr/` | Azure Pipelines | — |
| `repos/vscode-spring-boot-dashboard/` | Azure Pipelines | — |

### 4. Code Style & Linting

| Repo Path | Lint Command | Tool |
|------|-------------|------|
| `repos/vscode-java/` | `npm run eslint` | ESLint |
| `repos/vscode-java-debug/` | `npm run tslint` | TSLint |
| `repos/vscode-java-test/` | `npm run lint` | ESLint/TSLint |
| `repos/vscode-gradle/` | `./gradlew lint` (Prettier) | Prettier |
| `repos/vscode-java-dependency/` | `npm run tslint` | TSLint |
| `repos/vscode-maven/` | `npm run tslint` | TSLint |
| `repos/vscode-spring-initializr/` | `npm run tslint` | TSLint |
| `repos/vscode-spring-boot-dashboard/` | `npm run tslint` | ESLint |
| `repos/eclipse.jdt.core/` | `./mvnw checkstyle:check` | Checkstyle |
| `repos/java-debug/` | `./mvnw checkstyle:check` | Checkstyle |

### 5. Additional Requirements for Eclipse Projects

- **eclipse.jdt.ls**: Must sign the **Eclipse Contributor Agreement (ECA)**. Commits must include `Signed-off-by` (`git commit -s`).
- **eclipse.jdt.core**: Same ECA requirement. CI runs on Jenkins in addition to GitHub Actions.

### 6. Cross-Repo Impact Awareness

**Always use the canonical repo list** from the "Repositories in This Workspace" table above when performing cross-repo tasks (e.g., auditing Dependabot alerts, checking CI status, searching for patterns). Do **not** rely on which directories happen to exist locally — the workspace may contain only a subset of the repos. Use GitHub API tools (MCP, `gh`, or skill scripts) for metadata-only queries when no local source is needed. When local source is needed, follow the worktree setup above; absence from `repos/` alone does not mean no suitable clone or worktree exists.

Many features span multiple repos. Be aware of these common patterns:
- **Language features** (completion, diagnostics, refactoring): Changes typically go in `repos/eclipse.jdt.core/` or `repos/eclipse.jdt.ls/`, exposed to VS Code via `repos/vscode-java/`.
- **Debug features**: Client-side in `repos/vscode-java-debug/`, server-side in `repos/java-debug/`.
- **Test features**: Client-side in `repos/vscode-java-test/`, JDTLS plugin in the same repo.
- **Build tool features**: Maven in `repos/vscode-maven/`, Gradle in `repos/vscode-gradle/`, both integrate with `repos/eclipse.jdt.ls/` via JDTLS plugins.
- **JDTLS plugins**: Extensions contribute JARs via `contributes.javaExtensions` in `package.json`, loaded by `redhat.java` at startup. Changes to plugin APIs may require coordinated PRs across repos.

---

## GitHub Communication

When creating or drafting GitHub comments, pull requests, issues, reviews, or discussions, make code references, issue references, and PR references clickable markdown links to the real target when the target is known.

---

## Changelog Policy

Do not add or update a changelog in a feature or bug-fix contribution unless the user explicitly requests it or the repository's contributor documentation explicitly requires it. Recent maintainer commits that update the changelog do not establish a contributor requirement; leave release-note curation to maintainers by default. Version-bump and release-preparation tasks governed by `.github/instructions/version-bump.instructions.md` are exempt.

---

## Commit Messages

Always use [Conventional Commits](https://www.conventionalcommits.org/) when making commits (e.g., `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`, `ci:`). Use the format `<type>(<optional scope>): <description>`.

---

## Self-Evolution

When the user corrects your approach or you discover a gap in the agent configuration, **update the relevant config files** (instructions, skills, prompts) to prevent the same mistake in future sessions. See `.github/instructions/self-evolution.instructions.md` for the procedure and config manifest.
