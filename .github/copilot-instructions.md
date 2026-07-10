# Copilot Instructions — Java Extensions for VS Code

This workspace is a development environment for coding agents (GitHub Copilot, Claude Code, etc.) to work on **Java tooling for VS Code**. It may contain any subset of the repositories listed below — agents should clone the repos they need for the task at hand under `repos/`.

For detailed architecture, internal APIs, module maps, and communication patterns, see [Java-Tooling-Architecture.md](../javatooling-architecture.md).

---

## Pre-Work Repository Sync

Before starting any new issue investigation, bug fix, feature implementation, or other source-level work, ensure the relevant local repository is in sync with its original upstream default branch. If it is not in sync, use the `/sync-repos` prompt to sync that repo before continuing.

---

## Scratch Folder

The `scratch/` directory is a gitignored workspace for temporary files — extracted JARs, patched binaries, build artifacts for local testing, etc. Always use `scratch/` instead of creating ad-hoc folders in the workspace root. Contents are excluded from version control; only `.gitkeep` is tracked.

---

## Repository Folder

The `repos/` directory is the workspace home for all cloned Java tooling repositories and upstream dependencies. Keep the folder itself in the workspace with `repos/.gitkeep`, but keep cloned repositories ignored by version control. Do not clone Java tooling repositories into the workspace root.

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
| `repos/vscode-gradle/` | `./gradlew build testVsCode` | Mocha + JUnit + Gradle | Build JARs first: `cd extension && ../gradlew buildJars` |
| `repos/vscode-java-dependency/` | `npm run build-server && npm test` | Mocha + Maven | Build Java plugin first |
| `repos/vscode-maven/` | `npm run build-plugin && npm test` | Mocha + Maven | Build Java plugin first |
| `repos/vscode-spring-initializr/` | `npm test` | Mocha | — |
| `repos/vscode-spring-boot-dashboard/` | `npm test` | Mocha | Build Java plugin first: `npm run prepublish` |

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

**Always use the canonical repo list** from the "Repositories in This Workspace" table above when performing cross-repo tasks (e.g., auditing Dependabot alerts, checking CI status, searching for patterns). Do **not** rely on which directories happen to exist locally — the workspace may contain only a subset of the repos. For repos not cloned locally, use GitHub API tools (MCP, `gh`, or skill scripts) to query them, and clone only when changes are needed.

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

## Commit Messages

Always use [Conventional Commits](https://www.conventionalcommits.org/) when making commits (e.g., `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`, `ci:`). Use the format `<type>(<optional scope>): <description>`.

---

## Self-Evolution

When the user corrects your approach or you discover a gap in the agent configuration, **update the relevant config files** (instructions, skills, prompts) to prevent the same mistake in future sessions. See `.github/instructions/self-evolution.instructions.md` for the procedure and config manifest.
