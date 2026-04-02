# Java Tooling Architecture — Extension Pack for Java

This document describes the architecture, internal APIs, module maps, and communication patterns of the **Extension Pack for Java** in Visual Studio Code.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          VS Code (Editor)                               │
│                                                                         │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────┐ ┌─────────────────┐  │
│  │ vscode-maven │ │vscode-gradle │ │vscode-java │ │vscode-java-dep. │  │
│  │  (Maven UI)  │ │ (Gradle UI)  │ │  -debug    │ │  (Project Mgr)  │  │
│  └──────┬───────┘ └──────┬───────┘ └─────┬──────┘ └───────┬─────────┘  │
│         │                │               │                 │            │
│  ┌──────┴────────────────┴───────────────┴─────────────────┴─────────┐  │
│  │              vscode-java  (redhat.java)  — LSP Client             │  │
│  │              The central hub all extensions depend on             │  │
│  └──────────────────────────┬────────────────────────────────────────┘  │
│                             │  LSP (stdio / socket / pipe)             │
│  ┌──────────────────────────┴────────────────────────────────────────┐  │
│  │              vscode-java-test  (Test Runner)                      │  │
│  │              depends on both redhat.java & vscode-java-debug      │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                              │
              ════════════════╪══════════════════  (process boundary)
                              │
┌─────────────────────────────┴───────────────────────────────────────────┐
│              eclipse.jdt.ls  (Language Server — Java process)           │
│                                                                         │
│   Core:  LSP handlers, code completion, diagnostics, refactoring        │
│                                                                         │
│   Loaded JDTLS Plugins (contributed via javaExtensions):                │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ com.microsoft.java.debug.plugin    (from java-debug)            │   │
│   │ com.microsoft.java.test.plugin     (from vscode-java-test)      │   │
│   │ com.microsoft.jdtls.ext.core       (from vscode-java-dependency)│   │
│   │ com.microsoft.java.maven.plugin    (from vscode-maven)          │   │
│   │ com.microsoft.gradle.bs.importer   (from vscode-gradle)         │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│   Build Tool Integrations:                                              │
│   ┌──────────────┐  ┌──────────────────────────────────┐               │
│   │  M2Eclipse   │  │  Gradle Build Server (BSP)       │               │
│   │  (Maven)     │  │  build-server-for-gradle          │               │
│   └──────────────┘  └──────────────────────────────────┘               │
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │          eclipse.jdt.core  (Foundation Library)                  │   │
│   │                                                                  │   │
│   │  ┌──────────────────┐  ┌────────────┐  ┌──────────────────┐    │   │
│   │  │ Java Model       │  │ DOM / AST  │  │ Code Assist      │    │   │
│   │  │ (IJavaProject,   │  │ (ASTParser,│  │ (CompletionEngine │    │   │
│   │  │  ICompilationUnit│  │  ASTNode,  │  │  SelectionEngine) │    │   │
│   │  │  IType, IMethod) │  │  Bindings) │  │                   │    │   │
│   │  └──────────────────┘  └────────────┘  └──────────────────┘    │   │
│   │  ┌──────────────────┐  ┌────────────┐  ┌──────────────────┐    │   │
│   │  │ Search & Index   │  │ Formatter  │  │ ECJ Compiler     │    │   │
│   │  │ (SearchEngine,   │  │ (DefaultCo-│  │ (Parser, Codegen │    │   │
│   │  │  IndexManager)   │  │  deForma.) │  │  FlowAnalysis)   │    │   │
│   │  └──────────────────┘  └────────────┘  └──────────────────┘    │   │
│   └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Dependency Graph (Extension → Extension)

```
vscode-java-test
  ├── extensionDependencies: redhat.java
  └── extensionDependencies: vscjava.vscode-java-debug

vscode-java-debug
  └── extensionDependencies: redhat.java

vscode-gradle
  └── (runtime integration with redhat.java, no hard dependency)

vscode-java-dependency
  └── (runtime integration with redhat.java, no hard dependency)

vscode-maven
  └── (runtime integration with redhat.java, no hard dependency)

redhat.java  ←── Central hub, standalone, no extension dependencies
  └── embeds/downloads eclipse.jdt.ls as its language server

eclipse.jdt.ls  ←── Language Server, depends on eclipse.jdt.core
  └── org.eclipse.jdt.core (core library: compiler, model, AST, search, formatter)

eclipse.jdt.core  ←── Foundation library, no VS Code dependency
  ├── org.eclipse.jdt.core.compiler.batch (ECJ — standalone compiler, re-exported)
  ├── org.eclipse.jdt.core (model, DOM/AST, search, code assist, formatter)
  ├── org.eclipse.jdt.annotation (@Nullable/@NonNull annotations)
  └── org.eclipse.jdt.apt.* (annotation processing support)
```

---

## Detailed Project Descriptions

### 1. `vscode-java/` — Language Support for Java by Red Hat

- **Extension ID**: `redhat.java`
- **Version**: 1.54.0
- **Purpose**: The central Java extension. Provides code completion, diagnostics, navigation, refactoring, formatting, and project management for Java in VS Code.
- **Architecture**: LSP client (TypeScript) that spawns and communicates with `eclipse.jdt.ls` (Java).
- **Server modes**: Standard (full features), LightWeight (syntax only), Hybrid (auto-switch).
- **Build**: `npm install && npm run compile` (client), `npm run build-server` (server from source) or `npm run download-server` (pre-built binary).
- **Entry point**: `src/extension.ts` → bundled as `dist/extension.js`.
- **Key env var**: `JDT_LS_PATH` — point to local eclipse.jdt.ls build.

#### Exported API (ExtensionAPI v0.13)

Other extensions get this API via `vscode.extensions.getExtension('redhat.java').activate()`:

| API | Description |
|-----|-------------|
| `serverReady()` | Promise resolved when standard server is ready |
| `serverMode` | Current mode: Standard / Hybrid / LightWeight |
| `getProjectSettings(uri, keys)` | Get Java project compilation settings |
| `getClasspaths(uri, options)` | Get runtime/test classpaths and modulepaths |
| `isTestFile(uri)` | Check if file is in test source path |
| `onDidClasspathUpdate` | Event: project classpath changed |
| `onDidProjectsImport` | Event: projects imported |
| `onDidServerModeChange` | Event: server mode switched |

#### Key Settings Prefixes
- `java.jdt.ls.*` — Language server configuration (VM args, java home, features)
- `java.import.*` — Project import (Maven/Gradle toggles, exclusions)
- `java.configuration.*` — Runtimes, build configuration update behavior
- `java.completion.*`, `java.format.*` — Editor features
- `java.project.*` — Source paths, output paths, referenced libraries

#### JDTLS Plugin Loading Mechanism
Extensions declare JARs in their `package.json` under `contributes.javaExtensions`. When `redhat.java` activates, it collects all `javaExtensions` from installed extensions and passes them as bundles to `eclipse.jdt.ls` at startup.

---

### 2. `eclipse.jdt.ls/` — Eclipse JDT Language Server

- **Version**: 1.58.0-SNAPSHOT
- **License**: EPL 2.0
- **Purpose**: The Java language server implementing the Language Server Protocol (LSP). Powers all Java language features.
- **Runtime**: Requires Java 21+ to run.
- **Build**: `JAVA_HOME=/path/to/java21 ./mvnw clean verify -U`
- **Output**: `org.eclipse.jdt.ls.product/target/repository/` (Language Server + Syntax Server)

#### Key Modules
| Module | Purpose |
|--------|---------|
| `org.eclipse.jdt.ls.core` | Main server: LSP handlers, code analysis, refactoring, completions |
| `org.eclipse.jdt.ls.filesystem` | Virtual filesystem abstraction |
| `org.eclipse.jdt.ls.product` | Assembled product (language server + syntax server) |
| `org.eclipse.jdt.ls.tests` | Test suite with Maven/Gradle/Eclipse fixture projects |

#### Extension Points for Plugins
- **`org.eclipse.jdt.ls.core.delegateCommandHandler`** — Register custom commands handled by JDTLS plugins
- **`org.eclipse.jdt.ls.core.contentProvider`** — Register custom content providers (e.g., JAR file viewer)

#### Supported Project Types
- Maven (via M2Eclipse), Gradle (via Buildship), Eclipse (.project), Standalone Java files

#### Java-Specific LSP Extensions
- `java/classFileContents` — Decompile class files
- `java/projectConfigurationsUpdate` — Update project config
- `java/buildWorkspace` — Full workspace build

---

### 3. `eclipse.jdt.core/` — Eclipse JDT Core (Foundation Library)

- **Version**: 3.45.100 (parent POM: 4.40.0-SNAPSHOT)
- **License**: EPL 2.0
- **Purpose**: The foundational Java development tooling library. Provides the Java compiler (ECJ), Java model, AST/DOM, code assist, search/indexing, and formatter that `eclipse.jdt.ls` and the entire JDT ecosystem depend on.
- **Runtime**: Requires JavaSE-17 minimum.
- **Build**: Maven with Tycho — `./mvnw clean verify`
- **Repository**: https://github.com/eclipse-jdt/eclipse.jdt.core

#### Relationship to eclipse.jdt.ls
`eclipse.jdt.core` is the **core dependency** of `eclipse.jdt.ls`. The language server delegates nearly all Java intelligence to JDT Core:
- **Code completion** → `org.eclipse.jdt.internal.codeassist.CompletionEngine`
- **Diagnostics** → ECJ compiler (`org.eclipse.jdt.internal.compiler`)
- **Navigation** (go-to-definition, references) → `org.eclipse.jdt.core.search.SearchEngine`
- **Refactoring & code actions** → `org.eclipse.jdt.core.dom` (AST manipulation) + `org.eclipse.jdt.core.dom.rewrite`
- **Formatting** → `org.eclipse.jdt.internal.formatter.DefaultCodeFormatter`
- **Type hierarchy** → `org.eclipse.jdt.internal.core.hierarchy`
- **Java model** → `IJavaProject`, `ICompilationUnit`, `IType`, `IMethod`, `IField`

#### Module Map (16 modules)

| Module | Type | Purpose |
|--------|------|---------|
| **org.eclipse.jdt.core** | eclipse-plugin | Main module: Java model, DOM/AST, search, code assist, formatter |
| **org.eclipse.jdt.core.compiler.batch** | eclipse-plugin | Eclipse Compiler for Java (ECJ) — standalone batch compiler |
| **org.eclipse.jdt.core.formatterapp** | eclipse-plugin | Standalone Java code formatter application |
| **org.eclipse.jdt.annotation** | eclipse-plugin | Null-analysis annotations (@Nullable, @NonNull) — targets Java 1.8+ |
| **org.eclipse.jdt.apt.core** | eclipse-plugin | Annotation Processing Tool (old-style APT, pre-JSR 269) |
| **org.eclipse.jdt.apt.pluggable.core** | eclipse-plugin | JSR-269 Pluggable Annotation Processing bridge |
| **org.eclipse.jdt.apt.ui** | eclipse-plugin | UI for APT configuration (requires JavaSE-21) |
| **org.eclipse.jdt.core.internal.tools** | plugin fragment | Internal tools for compiler development |
| **org.eclipse.jdt.core.setup** | — | Eclipse Oomph setup configuration |
| **org.eclipse.jdt.core.tests.builder** | test | Incremental Java builder tests |
| **org.eclipse.jdt.core.tests.compiler** | test | Compiler parser and regression tests |
| **org.eclipse.jdt.core.tests.model** | test | Java element model tests (largest test suite) |
| **org.eclipse.jdt.core.tests.performance** | test | Performance benchmarking tests |
| **org.eclipse.jdt.apt.tests** | test | Old-style APT tests |
| **org.eclipse.jdt.apt.pluggable.tests** | test | JSR-269 annotation processing tests |
| **org.eclipse.jdt.compiler.tool.tests** | test | javax.tools API tests |

#### org.eclipse.jdt.core — Internal Architecture

The main module (~948 Java files) is organized into subsystems:

```
org.eclipse.jdt.core/
├── model/     (~515 files)  Java element model (workspace ↔ project ↔ packages ↔ types)
├── dom/       (~227 files)  AST/DOM nodes, bindings, rewriting
├── search/    (~152 files)  Search engine, indexing, pattern matching
├── codeassist/(~127 files)  Code completion and selection engines
├── formatter/ (~19 files)   Code formatting
├── eval/      (~26 files)   In-situ code evaluation
└── antadapter/(~2 files)    Ant task integration
```

#### Public API Packages

| Package | Key Types | Purpose |
|---------|-----------|---------|
| `org.eclipse.jdt.core` | `JavaCore`, `IJavaProject`, `ICompilationUnit`, `IType`, `IMethod`, `IField`, `IPackageFragment`, `IClasspathEntry` | Main Java model API — entry point for all JDT operations |
| `org.eclipse.jdt.core.dom` | `AST`, `ASTParser`, `ASTNode`, `CompilationUnit`, `ASTVisitor`, `IBinding`, `ITypeBinding`, `IMethodBinding` | Abstract Syntax Tree — parse, analyze, and transform Java source |
| `org.eclipse.jdt.core.dom.rewrite` | `ASTRewrite`, `ListRewrite` | Non-destructive AST modification producing TextEdits |
| `org.eclipse.jdt.core.search` | `SearchEngine`, `SearchPattern`, `IJavaSearchScope`, `IJavaSearchConstants` | Full-text and structural Java search |
| `org.eclipse.jdt.core.compiler` | `IProblem`, `ICompilerRequestor` | Compiler API — error/warning types and constants |
| `org.eclipse.jdt.core.formatter` | `DefaultCodeFormatterConstants`, `CodeFormatter` | Code formatting with 100+ configurable options |
| `org.eclipse.jdt.core.index` | Index infrastructure | On-disk index database for search |
| `org.eclipse.jdt.core.eval` | Evaluation context | Runtime code evaluation |
| `org.eclipse.jdt.core.util` | `IClassFileReader`, `IMethodInfo` | Class file reading and bytecode utilities |

#### Java Model Hierarchy

```
IJavaElement (base interface)
├── IJavaModel
│   └── IJavaProject
│       └── IPackageFragmentRoot (source folder / JAR)
│           └── IPackageFragment (package)
│               ├── ICompilationUnit (source .java file)
│               │   └── IType → IMethod, IField, IInitializer
│               └── IClassFile (binary .class file)
│                   └── IType → IMethod, IField
└── ITypeHierarchy (supertype/subtype graph)
```

**Entry Point**: `JavaCore` singleton — `JavaCore.create(project)` to get `IJavaProject`.

#### Eclipse Compiler for Java (ECJ) — `org.eclipse.jdt.core.compiler.batch`

ECJ is a full Java compiler that can run standalone (`java -jar ecj.jar *.java`) or embedded in the IDE. It supports Java 1.8 through Java 26.

| Package | Purpose |
|---------|---------|
| `o.e.jdt.internal.compiler` | Main `Compiler` class — orchestration |
| `o.e.jdt.internal.compiler.ast` | Compiler AST node types (different from DOM AST) |
| `o.e.jdt.internal.compiler.batch` | `Main` — command-line batch compilation entry |
| `o.e.jdt.internal.compiler.parser` | Recursive-descent Java parser and lexer |
| `o.e.jdt.internal.compiler.lookup` | Symbol table, scopes, type resolution |
| `o.e.jdt.internal.compiler.codegen` | `ClassFile` — bytecode generation |
| `o.e.jdt.internal.compiler.flow` | Data-flow analysis (null, unreachable code) |
| `o.e.jdt.internal.compiler.classfmt` | `ClassFileReader` — reading .class files |
| `o.e.jdt.internal.compiler.problem` | `ProblemReporter` — error/warning collection |
| `o.e.jdt.internal.compiler.apt` | Annotation Processing Tool (JSR 269) |
| `o.e.jdt.internal.compiler.tool` | `javax.tools` SPI integration (javac-compatible API) |

> **Note**: ECJ has its own AST (`o.e.jdt.internal.compiler.ast`) distinct from the DOM AST (`o.e.jdt.core.dom`). The DOM AST is the public API; the compiler AST is internal. JDTLS and refactoring tools use the DOM AST.

#### Code Assist Architecture

The code completion engine (`codeassist/`) uses a modified parser that can handle incomplete code:
- `CompletionParser` — parses partial/broken source at cursor position
- 60+ `CompletionOn*` context classes (e.g., `CompletionOnMemberAccess`, `CompletionOnMessageSend`, `CompletionOnSingleNameReference`)
- `CompletionEngine` — generates completion proposals from parsed context
- `SelectionEngine` — resolves element at cursor (for go-to-definition, hover)

#### Extension Points (plugin.xml)

| Extension Point | Purpose |
|-----------------|---------|
| `classpathVariableInitializer` | Dynamic classpath variables |
| `classpathContainerInitializer` | Classpath containers (JRE, user libraries) |
| `codeFormatter` | Third-party formatter registration |
| `compilationParticipant` | Compilation listeners/preprocessors |
| `compilationUnitResolver` | Custom compilation unit resolvers |
| `completionEngineProvider` | Custom code completion engines |
| `javaSearchDelegate` | Custom search implementations |
| `annotationProcessorManager` | APT manager |
| `javaFormatter` | Source formatter |

#### Bundle Dependencies
```
org.eclipse.jdt.core
├── org.eclipse.jdt.core.compiler.batch (re-exported — all compiler classes)
├── org.eclipse.core.resources [3.22.0, 4.0.0)
├── org.eclipse.core.runtime [3.29.0, 4.0.0)
├── org.eclipse.core.filesystem [1.11.0, 2.0.0)
├── org.eclipse.text [3.6.0, 4.0.0)
└── org.eclipse.team.core (optional)
```

#### Testing
Tests run across multiple Java compliance levels (`-Dcompliance=1.8|11|17|21|23|24|25|26`):
- `org.eclipse.jdt.core.tests.model` — Model tests (largest, 1800s timeout)
- `org.eclipse.jdt.core.tests.compiler` — Compiler regression tests (5400s timeout)
- `org.eclipse.jdt.core.tests.builder` — Incremental builder tests

---

### 4. `vscode-java-debug/` — Debugger for Java (VS Code Extension)

- **Extension ID**: `vscjava.vscode-java-debug`
- **Version**: 0.58.5
- **Purpose**: Provides Java debugging in VS Code using the Debug Adapter Protocol (DAP).
- **Hard dependency**: `redhat.java` (extensionDependencies)
- **Build**: `npm install && npm run compile` (client), `npm run build-server` (java-debug JAR)
- **Entry point**: `src/extension.ts` → bundled as `dist/extension.js`

#### Integration with redhat.java
- Calls JDTLS commands: `JAVA_START_DEBUGSESSION`, `JAVA_RESOLVE_CLASSPATH`, `JAVA_RESOLVE_MAINCLASS`, `JAVA_VALIDATE_LAUNCHCONFIG`
- Bundled JAR (`server/com.microsoft.java.debug.plugin-*.jar`) is loaded by JDTLS as a plugin

#### Debugger Type
- Registers VS Code debugger type: `"java"`
- Supports **Launch** and **Attach** configurations
- Features: breakpoints (line, conditional, data, exception), hot code replace, step filtering, inline values, no-config debug

#### Key Settings Prefix
- `java.debug.settings.*` — Debug display, HCR mode, code lens, JDWP timeout

#### Copilot Integration
- 8+ language model tools for AI-assisted debugging (e.g., `debug_java_application`, `set_java_breakpoint`, `get_debug_variables`)

---

### 5. `java-debug/` — Java Debug Server

- **Version**: 0.53.2
- **License**: EPL 1.0
- **Purpose**: Backend debug engine implementing DAP over JDI (Java Debug Interface). Runs as an Eclipse/JDTLS plugin.
- **Build**: `./mvnw clean verify` (requires JDK 21 for tests)

#### Key Modules
| Module | Purpose |
|--------|---------|
| `com.microsoft.java.debug.core` | Core debugger: DAP handlers, protocol, JDI integration |
| `com.microsoft.java.debug.plugin` | Eclipse/JDTLS plugin wrapper (OSGi bundle) |

#### Architecture Flow
```
VS Code Debug UI → vscode-java-debug (TS) → DAP over TCP socket → java-debug plugin (in JDTLS) → JVM (via JDI/JDWP)
```

#### Key Dependencies
- RxJava 2, GSON, Commons Lang3, Commons IO

---

### 6. `vscode-java-test/` — Test Runner for Java

- **Extension ID**: `vscjava.vscode-java-test`
- **Version**: 0.44.0
- **Purpose**: Run and debug Java tests with VS Code's Testing API.
- **Hard dependencies**: `redhat.java`, `vscjava.vscode-java-debug` (extensionDependencies)
- **Build**: `npm install && npm run compile` (client), `npm run build-plugin` (Java plugin)
- **Entry point**: `main.js`

#### Supported Test Frameworks
- JUnit 4 (≥4.8.0), JUnit 5 (≥5.1.0), JUnit 6 (≥6.0.1), TestNG (≥6.9.13.3)

#### Java-Side Components
| Component | Purpose |
|-----------|---------|
| `com.microsoft.java.test.plugin` | JDTLS plugin for test discovery and analysis |
| `com.microsoft.java.test.runner` | Standalone JAR for executing tests |

The plugin registers delegate commands: `vscode.java.test.get.testpath`, `vscode.java.test.junit.argument`, `vscode.java.test.findTestPackagesAndTypes`, `vscode.java.test.jacoco.getCoverageDetail`

#### Bundled JARs
26 JARs including JUnit 4/5/6 runtimes, JUnit Platform, TestNG, JaCoCo (code coverage), ASM

#### Key Settings Prefix
- `java.test.config` — Test launch configurations (args, vmArgs, env, classPaths, coverage)
- `java.test.defaultConfig` — Default configuration name

---

### 7. `vscode-gradle/` — Gradle for Java

- **Extension ID**: `vscjava.vscode-gradle`
- **Version**: 3.17.2
- **Purpose**: Gradle project management, task runner, and rich `.gradle` file editing.
- **No hard extension dependency**, but integrates with `redhat.java` at runtime.
- **Build**: `../gradlew buildJars` (Java servers), `./gradlew build testVsCode` (extension)
- **Entry point**: `extension/dist/index.js`

#### Three Server Components
| Component | Protocol | Purpose |
|-----------|----------|---------|
| Task Server | gRPC | Discover and execute Gradle tasks |
| Build Server | BSP (Build Server Protocol) | Provide build target info to JDTLS |
| Language Server | LSP | Code completion and diagnostics for `.gradle` files |

#### Communication
- Client ↔ Task Server: **gRPC**
- Client ↔ Build Server: **Named Pipes + JSON-RPC (BSP)**
- Client ↔ Language Server: **Named Pipes + LSP**
- JDTLS ↔ Build Server: **Build Server Protocol (BSP)**

#### JDTLS Integration
- Contributes `server/com.microsoft.gradle.bs.importer-*.jar` as a JDTLS plugin
- The importer connects to the Gradle Build Server and converts BSP BuildTargets into JDT projects
- Shares JDT workspace directory with `redhat.java`

#### Key Settings Prefixes
- `gradle.*` — Task detection, terminal reuse, debug, parallel run
- `java.gradle.buildServer.*` — Build server enable/disable, output behavior

#### Views
- `gradleTasksView` — Gradle project/task tree
- `recentTasksView` — Recently run tasks
- `gradleDaemonsView` — Daemon management

---

### 8. `vscode-gradle/extension/build-server-for-gradle/` — Build Server for Gradle

- **Purpose**: Implements the Build Server Protocol (BSP) for Gradle. Used by the vscode-gradle JDTLS importer to provide project structure to eclipse.jdt.ls.
- **Requires**: JDK 17+
- **Build**: Part of the vscode-gradle build (`../gradlew buildJars`)

#### Three Modules
| Module | Purpose |
|--------|---------|
| `model` | Shared interfaces between plugin and server |
| `plugin` | Gradle plugin injected via init script to extract project structure |
| `server` | BSP protocol implementation |

#### Transport
- Standard I/O (default) or Named Pipes (`--pipe=<pipeName>`)

#### Supported BSP Requests (29+)
`build/initialize`, `build/shutdown`, `buildTarget/sources`, `buildTarget/resources`, `buildTarget/compile`, `buildTarget/dependencyModules`, `buildTarget/javacOptions`, `workspace/buildTargets`, `workspace/reload`, and more.

---

### 9. `vscode-java-dependency/` — Project Manager for Java

- **Extension ID**: `vscjava.vscode-java-dependency`
- **Version**: 0.27.1
- **Purpose**: Java project explorer with project creation, library management, and JAR export.
- **No hard extension dependency**, but deeply integrates with `redhat.java` at runtime.
- **Build**: `npm install && npm run compile` (client), `npm run build-server` (Java plugin)
- **Entry point**: `extension.bundle.ts` → bundled as `dist/extension.bundle.js`

#### JDTLS Plugin
- `jdtls.ext/com.microsoft.jdtls.ext.core` — Provides delegate commands for project listing, package data, classpath info, JAR generation
- Delegate commands: `java.project.list`, `java.getPackageData`, `java.resolvePath`, `java.project.getMainClasses`, `java.project.generateJar`
- Content provider for `jdt://jarentry/.*` URIs

#### Views
- `javaProjectExplorer` — "Java Projects" tree view in Explorer sidebar (drag-drop, hierarchical/flat package view)

#### Key Features
- Create new Java projects, classes, interfaces, enums, records, annotations
- Add/remove libraries, export JARs
- Dependency upgrade notifications

#### Copilot Integration (Language Model Tools)
- `lsp_java_getFileStructure`, `lsp_java_findSymbol`, `lsp_java_getFileImports`, `lsp_java_getTypeAtPosition`, `lsp_java_getCallHierarchy`, `lsp_java_getTypeHierarchy`

#### Key Settings Prefix
- `java.dependency.*` — Explorer display options, auto-refresh, sync with file explorer
- `java.project.*` — JAR export target path, non-Java resources visibility

---

### 10. `vscode-maven/` — Maven for Java

- **Extension ID**: `vscjava.vscode-maven`
- **Version**: 0.45.1
- **Purpose**: Maven project explorer, POM editing, lifecycle/plugin goal execution, archetype support.
- **No hard extension dependency**, but deeply integrates with `redhat.java` at runtime.
- **Build**: `npm install && npm run compile` (client), `npm run build-plugin` (Java plugin)
- **Entry point**: `dist/extension`

#### JDTLS Plugin
- `jdtls.ext/com.microsoft.java.maven.plugin` — Provides delegate commands for artifact search and dependency management
- Delegate commands: `java.maven.initializeSearcher`, `java.maven.searchArtifact`, `java.maven.addDependency`, `java.maven.controlContext`

#### Integration with redhat.java
- Calls `java.projectConfiguration.update` when POM changes
- Registers artifact searcher when Java extension is enabled
- Can reuse `java.home` setting via `maven.terminal.useJavaHome`

#### Views
- `mavenProjects` — Maven project tree in Explorer sidebar (flat/hierarchical, profiles, dependencies with conflict detection, plugins, lifecycle phases)

#### Key Settings Prefix
- `maven.*` — Executable path, settings.xml, excluded folders, GAV completion, dependency diagnostics

---

## Cross-Cutting Patterns

### JDTLS Plugin Contribution Pattern
Most extensions contribute a Java-side component that runs inside `eclipse.jdt.ls`. The pattern is:

1. **Declare in `package.json`**: `"contributes": { "javaExtensions": ["./server/your-plugin.jar"] }`
2. **Implement in Java**: Create an Eclipse/OSGi plugin using `org.eclipse.jdt.ls.core.delegateCommandHandler` extension point
3. **Build with Maven (Tycho)**: The Java component uses Maven with Tycho for Eclipse plugin packaging
4. **Call from TypeScript**: Use `commands.executeCommand("java.execute.workspaceCommand", commandId, ...args)`

### Common Build Script Pattern
Most hybrid extensions follow this pattern:
```bash
# Build Java plugin
npm run build-server    # or build-plugin — runs Maven/Gradle to produce JARs

# Build TypeScript client
npm install
npm run compile         # Development build (tsc + webpack --mode development)
npm run watch           # Watch mode for development

# Production build
npm run vscode:prepublish  # webpack --mode production
```

### Communication Protocols
| Protocol | Used Between |
|----------|-------------|
| **LSP** (Language Server Protocol) | vscode-java ↔ eclipse.jdt.ls |
| **DAP** (Debug Adapter Protocol) | vscode-java-debug ↔ java-debug (over TCP socket) |
| **BSP** (Build Server Protocol) | vscode-gradle JDTLS importer ↔ build-server-for-gradle |
| **gRPC** | vscode-gradle client ↔ Gradle Task Server |
| **Delegate Commands** | All JDTLS plugins ↔ eclipse.jdt.ls (via `java.execute.workspaceCommand`) |

### Telemetry
- `redhat.java`: Red Hat telemetry (`@redhat-developer/vscode-redhat-telemetry`)
- Microsoft extensions: `vscode-extension-telemetry-wrapper` + `vscode-tas-client` (A/B testing)
