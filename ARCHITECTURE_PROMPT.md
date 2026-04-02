# Prompt: Generate Eclipse JDT Language Server Architecture Documentation

Use this prompt with GitHub Copilot (paste into chat with `@workspace` or an agent that has codebase access):

---

## The Prompt

```
@workspace Generate comprehensive markdown architecture documentation for Eclipse JDT Language Server (eclipse.jdt.ls). Structure the document with the sections below. For each section, reference actual class names, file paths, and code patterns from this codebase. Include ASCII diagrams or mermaid diagrams where helpful.

---

## Section 1: High-Level Architecture Overview

Document the overall system design:

- **Module structure**: Describe each OSGi bundle/plugin — `org.eclipse.jdt.ls.core` (main server), `org.eclipse.jdt.ls.filesystem` (virtual FS), `org.eclipse.jdt.ls.product` (distribution/packaging), `org.eclipse.jdt.ls.target` (target platform), `org.eclipse.jdt.ls.repository` (P2 repo).
- **Server modes**: Explain the two server modes — full Language Server (`LanguageServerApplication`) vs Syntax Server (`SyntaxServerApplication`), how they differ, and when each is used.
- **Startup sequence**: Trace the boot path from `LanguageServerApplication.start()` → `JavaLanguageServerPlugin.startLanguageServer()` → `JDTLanguageServer` creation → LSP4J JSON-RPC connection via socket/stdio/pipe. Reference `LanguageServerApplication.java`, `JavaLanguageServerPlugin.java`, `BaseJDTLanguageServer.java`.
- **LSP request dispatch**: Show how an incoming LSP JSON-RPC request flows through `JDTLanguageServer` (which implements LSP4J's `LanguageServer` interface) → delegated to specialized `*Handler` classes in `org.eclipse.jdt.ls.core.internal.handlers/` → resolved via JDT Core APIs → converted back to LSP4J response objects.
- **Dependency stack**: Eclipse Platform (OSGi, Resources, IWorkspace) → Eclipse JDT Core (compiler, model, search) → m2e (Maven) → Buildship (Gradle) → LSP4J (protocol) → Google Gson (serialization).

Include a layered architecture diagram.

---

## Section 2: Eclipse JDT Core Data Model

This is the most important section. Document the JDT element model that JDTLS wraps:

### 2.1 IJavaElement Hierarchy

Document the full `IJavaElement` type hierarchy that forms the backbone of the data model:

```
IJavaElement (root interface — all Java model elements)
├── IJavaModel           — The root, represents the entire Java workspace
├── IJavaProject         — A Java project with classpath, source folders, output
│   └── getResolvedClasspath() → IClasspathEntry[]
├── IPackageFragmentRoot — A source folder or library JAR/module root
│   ├── K_SOURCE         — Source folder (e.g., src/main/java)
│   └── K_BINARY         — JAR/class folder
├── IPackageFragment     — A package (e.g., com.example.util)
├── ITypeRoot (abstract)
│   ├── ICompilationUnit — Editable .java source file (working copy model)
│   └── IClassFile       — Read-only .class binary
├── IType                — Class, interface, enum, record, annotation type
│   ├── IMethod          — Method or constructor
│   ├── IField           — Field or enum constant
│   └── IInitializer     — Static or instance initializer block
└── ILocalVariable       — Local variable or parameter
```

Explain:
- **Working copy model**: How `ICompilationUnit` supports in-memory edits via `becomeWorkingCopy()`/`discardWorkingCopy()` for live editing without saving to disk. Reference `DocumentLifeCycleHandler.java` which manages open/change/save/close lifecycle.
- **How JDTLS resolves URIs to IJavaElements**: Trace `JDTUtils.resolveCompilationUnit(uri)` and `JDTUtils.resolveTypeRoot(uri)` — how a `file://` or `jdt://` URI gets mapped to an `ICompilationUnit` or `IClassFile`.
- **AST model**: How JDT's `CompilationUnit` AST (from `ASTParser`) differs from the `IJavaElement` model — the AST is a full syntax tree with `ASTNode` subclasses (`MethodDeclaration`, `TypeDeclaration`, `FieldDeclaration`, etc.), while `IJavaElement` is a lighter structural model.
- **Bindings**: How `IBinding`, `ITypeBinding`, `IMethodBinding`, `IVariableBinding` connect AST nodes to resolved type information.

### 2.2 LSP Wrapper Types

Document the custom LSP-facing data types JDTLS defines on top of the JDT model:
- `LspVariableBinding`, `LspMethodBinding` in `JdtDomModels.java`
- `ExtendedDocumentSymbol` in `DocumentSymbolHandler.java`
- How JDT elements get converted to LSP4J types (`Location`, `SymbolInformation`, `CompletionItem`, etc.)

### 2.3 IResource Model (Eclipse Platform Layer)

Explain how `IResource` (IProject, IFolder, IFile) from Eclipse Platform relates to `IJavaElement`:
- `IProject` ↔ `IJavaProject` (Java nature applied to platform project)
- `IFile` ↔ `ICompilationUnit` (Java nature on a .java file)
- `IWorkspace` / `IWorkspaceRoot` as the container

---

## Section 3: Classpath Architecture (Deep Dive)

### 3.1 IClasspathEntry Model

Document the five classpath entry kinds:
- `CPE_SOURCE` — Source folders (src/main/java, src/test/java)
- `CPE_LIBRARY` — JAR files, class folders, JRT modules
- `CPE_PROJECT` — Inter-project dependencies
- `CPE_VARIABLE` — Path variables (e.g., M2_REPO)
- `CPE_CONTAINER` — Classpath containers (JRE System Library, Maven Dependencies, Gradle classpath)

Explain `IClasspathContainer` and how containers like `org.eclipse.jdt.launching.JRE_CONTAINER` and `org.eclipse.m2e.MAVEN2_CLASSPATH_CONTAINER` lazily resolve to actual JAR paths.

### 3.2 Classpath Resolution Flow

Trace the full classpath lifecycle:

1. **Project discovery**: `ProjectsManager.initializeProjects()` scans workspace roots for build files
2. **Project import**: Appropriate `IProjectImporter` is selected:
   - `MavenProjectImporter` — detects `pom.xml`, uses m2e to create IJavaProject with Maven classpath container
   - `GradleProjectImporter` — detects `build.gradle`/`settings.gradle`, uses Buildship for Gradle classpath
   - `EclipseProjectImporter` — detects `.project` + `.classpath`, reads raw classpath directly
   - `InvisibleProjectImporter` — no build file detected, creates synthetic project wrapping loose .java files
3. **Classpath container resolution**: m2e/Buildship resolve containers → actual JARs from local repository/cache
4. **Classpath update propagation**: `UpdateClasspathJob` applies changes → `ClasspathUpdateHandler` listens via `IElementChangedListener` → publishes classpath diagnostics to LSP client
5. **Incremental updates**: When `pom.xml` or `build.gradle` changes → `IBuildSupport.fileChanged()` → re-import → classpath refresh

Include a sequence diagram of this flow.

### 3.3 IBuildSupport System

Document the build tool abstraction:

```java
IBuildSupport {
    boolean applies(IProject project);
    boolean isBuildFile(IResource resource);
    void update(IProject project, boolean force, IProgressMonitor monitor);
    void fileChanged(IResource resource, CHANGE_TYPE changeType, IProgressMonitor monitor);
    String buildToolName();
}
```

Implementations: `MavenBuildSupport`, `GradleBuildSupport`, `EclipseBuildSupport`, `InvisibleProjectBuildSupport`. Explain how `BuildSupportManager` selects the right implementation. Reference the `org.eclipse.jdt.ls.core.buildSupport` extension point.

### 3.4 Maven Classpath Details

- How m2e resolves `pom.xml` → `MavenProject` → `IClasspathEntry[]`
- `MAVEN2_CLASSPATH_CONTAINER` contents: compile, runtime, test scopes
- Source attachment: `MavenSourceDownloader` resolves source JARs
- Multi-module projects: Parent POM discovery, reactor dependencies

### 3.5 Gradle Classpath Details

- How Buildship resolves `build.gradle` → `EclipseProject` model → `IClasspathEntry[]`
- Custom init scripts in `org.eclipse.jdt.ls.core/gradle/`: `android/`, `kotlin/`, `groovy/`, `protobuf/`, `apt/`
- Gradle wrapper detection and version management
- Composite builds and included builds

### 3.6 Invisible Project Mode

Explain how JDTLS handles standalone .java files with no build descriptor:
- `InvisibleProjectBuildSupport` creates a synthetic Eclipse project
- Library detection: scans for JARs in workspace, adds to classpath
- JDK selection: `java.configuration.runtimes` setting → JRE classpath container
- Limitations compared to Maven/Gradle mode

### 3.7 Classpath Commands

Document the LSP commands exposed for classpath management:
- `BuildPathCommand.listSourcePaths()` / `addToSourcePath()` / `removeFromSourcePath()`
- `ProjectCommand.getClasspathsFromProject()` — returns full resolved classpath
- `SourceAttachmentCommand` — attach/update source JARs for debugging

---

## Section 4: Project Management Lifecycle

Document `ProjectsManager` / `StandardProjectsManager`:
- Workspace folder initialization and multi-root workspace support
- `registerWatchers()` — file system watcher registration for build files
- Resource change listeners: how file saves trigger builds
- `updateProject()` flow and debouncing via `UpdateProjectsJob`
- Workspace folder add/remove handling

---

## Section 5: LSP Handler Architecture

### 5.1 Handler Pattern

Document how each LSP request maps to a handler:
- `JDTLanguageServer` as the routing layer (reference actual method signatures)
- Handler instantiation: stateless handlers created per request vs shared instances
- Common pattern: URI → `JDTUtils.resolveCompilationUnit()` → JDT API call → LSP result conversion

### 5.2 Key Handler Flows

Provide detailed flows for:
- **Completion**: `CompletionHandler` → `ICompilationUnit.codeComplete()` → `CompletionProposalRequestor` → `CompletionItem[]`
- **Diagnostics**: `DiagnosticsHandler` → JDT problem markers from build → `PublishDiagnosticsParams`
- **Navigation** (definition/references): `NavigateToDefinitionHandler` → `IJavaElement` resolution → `Location`
- **Code Actions**: `CodeActionHandler` → `QuickFixProcessor` (quick fixes) + `RefactorProcessor` (refactorings) → `CodeAction[]`

### 5.3 Document Lifecycle

Trace `DocumentLifeCycleHandler`:
- `didOpen` → create working copy
- `didChange` → apply incremental text edits to buffer
- `didSave` → reconcile, trigger build
- `didClose` → discard working copy

---

## Section 6: Extension Point System

Document the 4 extension points defined in `plugin.xml` and their schemas:
- `org.eclipse.jdt.ls.core.buildSupport` — pluggable build tools
- `org.eclipse.jdt.ls.core.importers` — pluggable project importers
- `org.eclipse.jdt.ls.core.contentProvider` — pluggable source/decompiler providers (mention `FernFlowerDecompiler`)
- `org.eclipse.jdt.ls.core.delegateCommandHandler` — pluggable custom LSP commands

Explain how third-party Eclipse plugins can extend JDTLS capabilities.

---

## Section 7: Configuration & Preferences

Document the preferences system:
- `PreferenceManager` → `Preferences` object
- `ClientPreferences` — LSP client capabilities
- Key settings: `java.home`, `java.configuration.runtimes`, `java.import.gradle.*`, `java.import.maven.*`, `java.format.*`
- How preferences affect classpath resolution (e.g., `java.configuration.runtimes` → JRE container)

---

## Section 8: Key Utility Classes

Document the critical utility classes that glue everything together:
- `JDTUtils` — URI↔IJavaElement resolution, position conversion, document access
- `ProjectUtils` — project capability queries (isJavaProject, hasNature, etc.)
- `ResourceUtils` — file/resource operations
- `JavaElementLabels` / `JavaElementLabelComposer` — human-readable element labels

---

Format the entire document as a single well-structured markdown file with a table of contents, mermaid diagrams for architecture/sequence flows, and code snippets showing key interfaces. Target 3000-5000 words. Use tables for handler/class mappings and tree diagrams for hierarchies.
```

---

## Tips for Best Results

1. **Use `@workspace`** so Copilot has full codebase context
2. **Generate section by section** if the full output is too long — ask for "Section 3: Classpath Architecture" separately
3. **Follow up with specifics** like:
   - "Show me the actual code flow when a pom.xml changes and classpath gets updated"
   - "What happens when JDTLanguageServer receives a textDocument/completion request? Trace through every class"
   - "How does InvisibleProjectBuildSupport decide which JARs to put on the classpath?"
4. **Ask for diagrams**: "Generate a mermaid sequence diagram showing the Maven classpath resolution flow"
