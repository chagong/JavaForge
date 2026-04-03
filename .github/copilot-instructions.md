# Copilot Instructions — Java Extensions for VS Code

This workspace is a development environment for coding agents (GitHub Copilot, Claude Code, etc.) to work on **Java tooling for VS Code**. It may contain any subset of the repositories listed below — agents should clone the repos they need for the task at hand.

For detailed architecture, internal APIs, module maps, and communication patterns, see [Java-Tooling-Architecture.md](../Java-Tooling-Architecture.md).

---

## Repositories in This Workspace

| Folder | Role | Repository |
|--------|------|------------|
| `vscode-java/` | Java Language Support — LSP client (TypeScript), central hub extension | https://github.com/redhat-developer/vscode-java |
| `eclipse.jdt.ls/` | Eclipse JDT Language Server — LSP server powering all Java language features (Java) | https://github.com/eclipse-jdtls/eclipse.jdt.ls |
| `eclipse.jdt.core/` | Eclipse JDT Core — compiler (ECJ), Java model, AST, search, formatter (Java) | https://github.com/eclipse-jdt/eclipse.jdt.core |
| `vscode-java-debug/` | Debugger for Java — DAP client extension (TypeScript) | https://github.com/microsoft/vscode-java-debug |
| `java-debug/` | Java Debug Server — DAP server over JDI (Java) | https://github.com/microsoft/java-debug |
| `vscode-java-test/` | Test Runner for Java — VS Code Testing API integration (TypeScript + Java) | https://github.com/microsoft/vscode-java-test |
| `vscode-gradle/` | Gradle for Java — project management, task runner, `.gradle` editing (TypeScript + Java) | https://github.com/microsoft/vscode-gradle |
| `vscode-gradle/extension/build-server-for-gradle/` | Build Server for Gradle — BSP server, sub-project of vscode-gradle (Java) | https://github.com/microsoft/build-server-for-gradle |
| `vscode-java-dependency/` | Project Manager for Java — project explorer, library management, JAR export (TypeScript + Java) | https://github.com/microsoft/vscode-java-dependency |
| `vscode-maven/` | Maven for Java — project explorer, POM editing, lifecycle execution (TypeScript + Java) | https://github.com/microsoft/vscode-maven |

---

## VS Code Extensions ↔ Repository Mapping

| Extension ID | Extension Name | VS Code Extension Repo | Backend/Server Repo |
|-------------|---------------|----------------------|---------------------|
| `redhat.java` | Language Support for Java | `vscode-java/` | `eclipse.jdt.ls/` + `eclipse.jdt.core/` |
| `vscjava.vscode-java-debug` | Debugger for Java | `vscode-java-debug/` | `java-debug/` |
| `vscjava.vscode-java-test` | Test Runner for Java | `vscode-java-test/` | (Java plugin in same repo) |
| `vscjava.vscode-gradle` | Gradle for Java | `vscode-gradle/` | (Java servers in same repo) |
| `vscjava.vscode-java-dependency` | Project Manager for Java | `vscode-java-dependency/` | (Java plugin in same repo) |
| `vscjava.vscode-maven` | Maven for Java | `vscode-maven/` | (Java plugin in same repo) |

### Extension Dependency Chain

- `vscode-java-test` → depends on `redhat.java` + `vscjava.vscode-java-debug`
- `vscode-java-debug` → depends on `redhat.java`
- `vscode-gradle`, `vscode-java-dependency`, `vscode-maven` → runtime integration with `redhat.java` (no hard dependency)
- `redhat.java` → embeds `eclipse.jdt.ls` which depends on `eclipse.jdt.core`

---

## Constraints for Resolving Issues and Feature Requests

When working on bug fixes or feature requests for any repo in this workspace, all changes **must** satisfy the following requirements before a PR is considered ready:

### 1. Unit Tests Must Pass

Every repo has unit tests that must pass locally before submitting a PR.

| Repo | Test Command | Build System | Notes |
|------|-------------|-------------|-------|
| `vscode-java` | `npm test` | Mocha | Requires X11 on Linux (`xvfb-run`) |
| `eclipse.jdt.ls` | `./mvnw clean verify` | JUnit (OSGi plugin tests) | Requires JDK 21+ |
| `eclipse.jdt.core` | `./mvnw clean verify` | JUnit (OSGi plugin tests) | Multi-compliance: Java 8, 11, 17, 21, 25, 26 |
| `vscode-java-debug` | `npm test` | Mocha | — |
| `java-debug` | `./mvnw clean verify` | JUnit 4 + EasyMock | Requires JDK 21+ |
| `vscode-java-test` | `npm run build-plugin && npm test` | Mocha + Maven | Build Java plugin first |
| `vscode-gradle` | `./gradlew build testVsCode` | Mocha + JUnit + Gradle | Build JARs first: `cd extension && ../gradlew buildJars` |
| `vscode-java-dependency` | `npm run build-server && npm test` | Mocha + Maven | Build Java plugin first |
| `vscode-maven` | `npm run build-plugin && npm test` | Mocha + Maven | Build Java plugin first |

### 2. UI Tests Must Pass (Where Applicable)

Some repos have dedicated UI test workflows that validate end-to-end behavior:

| Repo | UI Test Workflow | Platforms |
|------|-----------------|-----------|
| `vscode-java-dependency` | `windowsUI.yml`, `linuxUI.yml` | Windows, Linux |

### 3. PR CI Checks Must Pass

Every repo runs CI on pull requests. A PR cannot be merged until all CI checks are green.

| Repo | CI Workflows | Platforms |
|------|-------------|-----------|
| `vscode-java` | `pr-verify.yml` — build, lint (`eslint`), test, package | macOS, Linux |
| `eclipse.jdt.core` | `ci.yml` — full verify; `pr-checks.yml`; `codeql.yml` | Linux, Windows, macOS |
| `eclipse.jdt.ls` | `licensecheck.yml` — license vetting; `codeql-analysis.yml` | Linux |
| `vscode-java-debug` | `build.yml` — lint (`tslint`), build, test, package | Linux |
| `java-debug` | `build.yml` — verify + checkstyle | Linux, Windows |
| `vscode-java-test` | `build.yml` — build-plugin, lint, compile, test, package | Linux |
| `vscode-gradle` | `main.yml` — build, lint, test, SonarQube analysis | Ubuntu |
| `vscode-java-dependency` | `linux.yml`, `windows.yml`, `macOS.yml`, `linuxUI.yml`, `windowsUI.yml` | Linux, Windows, macOS |
| `vscode-maven` | `linux.yml`, `windows.yml`, `macOS.yml` | Linux, Windows, macOS |

### 4. Code Style & Linting

| Repo | Lint Command | Tool |
|------|-------------|------|
| `vscode-java` | `npm run eslint` | ESLint |
| `vscode-java-debug` | `npm run tslint` | TSLint |
| `vscode-java-test` | `npm run lint` | ESLint/TSLint |
| `vscode-gradle` | `./gradlew lint` (Prettier) | Prettier |
| `vscode-java-dependency` | `npm run tslint` | TSLint |
| `vscode-maven` | `npm run tslint` | TSLint |
| `eclipse.jdt.core` | `./mvnw checkstyle:check` | Checkstyle |
| `java-debug` | `./mvnw checkstyle:check` | Checkstyle |

### 5. Additional Requirements for Eclipse Projects

- **eclipse.jdt.ls**: Must sign the **Eclipse Contributor Agreement (ECA)**. Commits must include `Signed-off-by` (`git commit -s`).
- **eclipse.jdt.core**: Same ECA requirement. CI runs on Jenkins in addition to GitHub Actions.

### 6. Cross-Repo Impact Awareness

Many features span multiple repos. Be aware of these common patterns:
- **Language features** (completion, diagnostics, refactoring): Changes typically go in `eclipse.jdt.core` or `eclipse.jdt.ls`, exposed to VS Code via `vscode-java`.
- **Debug features**: Client-side in `vscode-java-debug`, server-side in `java-debug`.
- **Test features**: Client-side in `vscode-java-test`, JDTLS plugin in the same repo.
- **Build tool features**: Maven in `vscode-maven`, Gradle in `vscode-gradle`, both integrate with `eclipse.jdt.ls` via JDTLS plugins.
- **JDTLS plugins**: Extensions contribute JARs via `contributes.javaExtensions` in `package.json`, loaded by `redhat.java` at startup. Changes to plugin APIs may require coordinated PRs across repos.
