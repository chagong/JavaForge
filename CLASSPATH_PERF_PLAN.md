# Plan: JDTLS Classpath Performance Improvements

## TL;DR
Improve classpath handling performance for large projects (thousands of dependencies/modules) by fixing six bottlenecks: DigestStore serialization thrashing, uncached build support instantiation, single-threaded event processing, O(n×m) working copy scanning, Gradle-global APT sync, and hard-barrier job throttling. Changes are grouped into 3 phases: quick wins, moderate refactors, and larger architectural improvements.

---

## Phase 1: Quick Wins (no architectural changes, high impact)

### Step 1.1 — Cache `buildSupports()` in StandardProjectsManager
**What:** `buildSupports()` (L431-L444) calls `createExecutableExtension()` on every invocation (7+ call sites). `BuildSupportManager.obtainBuildSupports()` already caches via `lazyLoadedBuildSupportList` but is not used.
**Change:** Replace `buildSupports()` body to delegate to `BuildSupportManager.obtainBuildSupports().stream()`, or cache locally in a field.
**Files:**
- `org.eclipse.jdt.ls.core/src/org/eclipse/jdt/ls/core/internal/managers/StandardProjectsManager.java` — modify `buildSupports()` at L431-L444
**Risk:** Low. Build supports are stateless singletons.

### Step 1.2 — Batch DigestStore serialization (deferred flush)
**What:** `DigestStore.updateDigest()` (L64-L80) calls `serializeFileDigests()` on every single digest change, writing the entire HashMap via ObjectOutputStream. During Gradle import of N projects, this means up to 4N full serializations.
**Change:**
- Add a `dirty` flag instead of serializing immediately
- Add `flush()` method that serializes only if dirty
- Add `updateDigests(Collection<Path>)` batch method that computes all digests, updates the map once, serializes once
- Call `flush()` at checkpoint boundaries (end of import in GradleProjectImporter L249-269, end of MavenProjectImporter import, and in a shutdown hook)
- Replace individual `updateDigest()` calls in GradleProjectImporter post-import loop (L249-269) and GradleBuildSupport.update() (L147-150) with batch calls
**Files:**
- `org.eclipse.jdt.ls.core/src/org/eclipse/jdt/ls/core/internal/managers/DigestStore.java` — add `dirty` flag, `flush()`, `updateDigests(Collection<Path>)`, defer serialization
- `org.eclipse.jdt.ls.core/src/org/eclipse/jdt/ls/core/internal/managers/GradleProjectImporter.java` — L249-269: replace individual updateDigest calls with batch
- `org.eclipse.jdt.ls.core/src/org/eclipse/jdt/ls/core/internal/managers/GradleBuildSupport.java` — L147-150: collect paths, call batch update
- `org.eclipse.jdt.ls.core/src/org/eclipse/jdt/ls/core/internal/JavaLanguageServerPlugin.java` — ensure `flush()` is called on shutdown
**Risk:** Medium. Must ensure flush is called before process exit to avoid losing state. Add a shutdown hook or call from `JavaLanguageServerPlugin.stop()`.

### Step 1.3 — Optimize DigestStore internals
**What:** `computeDigest()` (L100-104) allocates a new `MessageDigest` per call and reads entire file into memory. String representation uses `Arrays.toString()` (slow, verbose).
**Change:**
- Use `ThreadLocal<MessageDigest>` to reuse MD5 instance (call `reset()`)
- Use `DigestInputStream` + streaming instead of `Files.readAllBytes()` for large files
- Replace `Arrays.toString(byte[])` with hex encoding (HexFormat in Java 17+)
- Replace `ObjectOutputStream` serialization with a simple line-based format (path=hex per line) — faster, human-readable, no ClassNotFoundException risk
**Files:**
- `org.eclipse.jdt.ls.core/src/org/eclipse/jdt/ls/core/internal/managers/DigestStore.java` — rewrite `computeDigest()`, `serializeFileDigests()`, `deserializeFileDigests()`
**Depends on:** Step 1.2 (batch flush design)
**Risk:** Medium. Must handle migration from old serialization format (catch on deserialize, fall back to empty map — which is already the behavior on error).

### Step 1.4 — Replace busy-wait in WorkspaceEventsHandler
**What:** Constructor thread (L54-68) busy-polls `pm.isBuildFinished()` with `Thread.sleep(200)`.
**Change:** Add a `CountDownLatch` or `ReentrantLock+Condition` in `ProjectsManager` that is signaled when build finishes. Replace sleep loop with `latch.await()` or `condition.await()`.
**Files:**
- `org.eclipse.jdt.ls.core/src/org/eclipse/jdt/ls/core/internal/handlers/WorkspaceEventsHandler.java` — L57-62: replace sleep loop
- `org.eclipse.jdt.ls.core/src/org/eclipse/jdt/ls/core/internal/managers/ProjectsManager.java` — add signaling mechanism (e.g., expose a `awaitBuildFinished()` method using CountDownLatch)
**Risk:** Low. The existing behavior is a correctness antipattern.

---

## Phase 2: Moderate Refactors (targeted structural changes)

### Step 2.1 — Batch event processing in WorkspaceEventsHandler
**What:** Events are processed one at a time via `queue.take()`. No coalescing of duplicate events.
**Change:**
- Replace `queue.take()` with `queue.drainTo(batch, MAX_BATCH_SIZE)` (with `queue.take()` for the first element to block efficiently)
- Coalesce: for the same URI, keep only the latest event type (CHANGED supersedes CREATED; DELETED supersedes all)
- Group build-file events and call `pm.fileChanged()` once per unique URI
**Files:**
- `org.eclipse.jdt.ls.core/src/org/eclipse/jdt/ls/core/internal/handlers/WorkspaceEventsHandler.java` — refactor event loop in constructor thread (L57-67) and `handleFileEvent()` (L104-138) into a batch `handleFileEvents(List<FileEvent>)` method
**Depends on:** Step 1.4 (busy-wait removal)
**Risk:** Medium. Must preserve ordering semantics for DELETE events (delete before create = rename). Test with `handleFileEvents()` test helper (L93-97) which already exists.

### Step 2.2 — Per-project working copy index in ClasspathUpdateHandler
**What:** `elementChanged()` (L68-78) iterates all working copies globally via `JavaCore.getWorkingCopies(null)` and filters per project — O(totalWorkingCopies × changedProjects).
**Change:**
- Maintain a `Map<IJavaProject, Set<ICompilationUnit>>` in `BaseDocumentLifeCycleHandler` (or a helper class)
- Update on `didOpen`/`didClose`
- In ClasspathUpdateHandler, look up directly: `lifeCycleHandler.getWorkingCopies(javaProject)` → O(1) per project
**Files:**
- `org.eclipse.jdt.ls.core/src/org/eclipse/jdt/ls/core/internal/handlers/BaseDocumentLifeCycleHandler.java` — add per-project working copy map and accessors
- `org.eclipse.jdt.ls.core/src/org/eclipse/jdt/ls/core/internal/handlers/ClasspathUpdateHandler.java` — L68-78: use new accessor instead of iterating global working copies
**Risk:** Low-Medium. Must ensure map is updated correctly on project delete/close.

### Step 2.3 — Semaphore-based job throttling
**What:** `waitForUpdateJobs()` (ProjectsManager.java L520-525) blocks on ALL update jobs when count exceeds threshold — hard barrier instead of smooth throttling.
**Change:** Replace with `Semaphore(maxConcurrentBuilds)` acquired before `job.schedule()` and released in the job's `done()` callback. Remove `waitForUpdateJobs()`.
**Files:**
- `org.eclipse.jdt.ls.core/src/org/eclipse/jdt/ls/core/internal/managers/ProjectsManager.java` — L487-532: add Semaphore field, acquire in `updateProject()`/`updateProjects()`, release in job completion listener
**Risk:** Medium. Must handle job cancellation (release semaphore in finally/done). Must respect preference changes to `maxConcurrentBuilds` (recreate semaphore).

---

## Phase 3: Larger Improvements (architectural, higher effort)

### Step 3.1 — Scope Gradle APT sync to affected projects
**What:** `syncAnnotationProcessingConfiguration()` (GradleBuildSupport.java L188-254) queries the Gradle model for ALL projects on every single update, even when only one build file changed.
**Change:**
- Filter projects to only those affected by the current build file change (the project being updated + direct dependents if needed)
- Cache APT configuration per project; only re-query when that project's own build file digest changes
**Files:**
- `org.eclipse.jdt.ls.core/src/org/eclipse/jdt/ls/core/internal/managers/GradleBuildSupport.java` — L188-270: add project filtering and caching
**Risk:** Medium-High. Must ensure cache invalidation is correct when transitive dependencies change APT configuration.

### Step 3.2 — Incremental watcher registration
**What:** `registerWatchers()` (StandardProjectsManager.java L467-579) iterates all projects × all classpath entries every time. Called after every project update.
**Change:**
- Cache the computed watcher pattern set
- On classpath change events (from ClasspathUpdateHandler), compute delta patterns for only the changed project
- Only re-register watchers if the pattern set actually changed
**Files:**
- `org.eclipse.jdt.ls.core/src/org/eclipse/jdt/ls/core/internal/managers/StandardProjectsManager.java` — L467-579: add pattern caching, delta computation
**Depends on:** Step 1.1 (cached buildSupports)
**Risk:** Medium. Must handle project deletion (remove stale patterns).

### Step 3.3 — Parallel Gradle project imports
**What:** `GradleProjectImporter.importToWorkspace()` (L224-248) imports directories sequentially, each blocking on `gradleBuild.synchronize()`.
**Change:**
- Detect independent Gradle builds (separate `settings.gradle` roots)
- Import independent builds in parallel using a bounded thread pool
- Keep sequential import within a single Gradle build (modules share a daemon)
**Files:**
- `org.eclipse.jdt.ls.core/src/org/eclipse/jdt/ls/core/internal/managers/GradleProjectImporter.java` — L224-248: parallelize `importDir()` loop for independent builds
**Risk:** High. Buildship/Gradle daemon may not support concurrent synchronization well. Needs careful testing.

---

## Relevant Files Summary

| File | Phase | What to change |
|------|-------|----------------|
| `org.eclipse.jdt.ls.core/.../managers/DigestStore.java` | 1.2, 1.3 | Batch flush, streaming hash, format migration |
| `org.eclipse.jdt.ls.core/.../managers/StandardProjectsManager.java` | 1.1, 3.2 | Cache buildSupports(), incremental watchers |
| `org.eclipse.jdt.ls.core/.../handlers/WorkspaceEventsHandler.java` | 1.4, 2.1 | Remove busy-wait, batch events |
| `org.eclipse.jdt.ls.core/.../handlers/ClasspathUpdateHandler.java` | 2.2 | Per-project working copy lookup |
| `org.eclipse.jdt.ls.core/.../handlers/BaseDocumentLifeCycleHandler.java` | 2.2 | Add per-project working copy index |
| `org.eclipse.jdt.ls.core/.../managers/ProjectsManager.java` | 1.4, 2.3 | Build-finished signal, semaphore throttling |
| `org.eclipse.jdt.ls.core/.../managers/GradleBuildSupport.java` | 1.2, 3.1 | Batch digest, scoped APT sync |
| `org.eclipse.jdt.ls.core/.../managers/GradleProjectImporter.java` | 1.2, 3.3 | Batch digest, parallel imports |
| `org.eclipse.jdt.ls.core/.../JavaLanguageServerPlugin.java` | 1.2 | Flush digest store on shutdown |

## Verification

1. **Unit tests for DigestStore:** Create `org.eclipse.jdt.ls.tests/.../managers/DigestStoreTest.java` — test batch update, deferred flush, format migration from old ObjectOutputStream format
2. **Existing ClasspathUpdateHandlerTest:** Run after Step 2.2 changes — all 4 tests must pass (testClasspathUpdateForMaven, testClasspathUpdateForGradle, testClasspathUpdateForEclipse, testClasspathUpdateForInvisble)
3. **Full build:** `.\mvnw.cmd clean -B package` must pass
4. **Integration verification:** `.\mvnw.cmd -B verify` must pass
5. **Manual perf validation:** Open a large multi-module Maven/Gradle project, measure time from `initialize` to `Projects imported` in JDTLS log before and after changes
6. **Regression:** Modify a `pom.xml` or `build.gradle` in a large project and verify classpath update still triggers correctly (digest store changes are the riskiest)

## Decisions
- Phase 1 steps are independent of each other and can be implemented in parallel
- Phase 2 steps depend on Phase 1 completions as noted
- Phase 3 steps are optional stretch goals, higher risk
- DigestStore format migration: fall back to empty map on deserialization failure (existing behavior), so old format is handled gracefully
- No new user-facing settings are needed; existing `java.maxConcurrentBuilds` is sufficient

---

## Section 4: Project Initialization Deep Dive

This section documents what actually happens during project initialization, from the LSP `initialize` request to the point where the server sends `ServiceStatus.Started ("Ready")`.

### 4.1 — Full Initialization Call Chain

The initialization flow is triggered from `InitHandler.triggerInitialization()` which schedules a `WorkspaceJob` with `BUILD` priority, locked on the workspace root:

```
Client sends "initialize" request
  └─ InitHandler.initialize()
       ├─ handleInitializationOptions()     — parse roots, settings, capabilities
       │    ├─ JVMConfigurator.configureJVMs()  — discover/register JDKs
       │    └─ registerWorkspaceInitialized()   — mark workspace as initialized
       └─ triggerInitialization(rootPaths)   — schedules WorkspaceJob (async)
            └─ WorkspaceJob "Initialize Workspace" (runs in workspace thread)
                 ├─ PHASE A: waitForRepositoryRegistryUpdateJob()   — blocks up to 300s
                 ├─ interruptAutoBuild()                            — suppress auto-build during import
                 ├─ PHASE B: projectsManager.initializeProjects()   — THE MAIN WORK
                 │    ├─ cleanInvalidProjects()                     — 20% of monitor
                 │    │    ├─ deleteInvalidProjects()               — remove stale projects from workspace
                 │    │    └─ GradleBuildSupport.cleanGradleModels() — purge orphan Gradle model files
                 │    ├─ (if empty roots) createDefaultJavaProject  — create jdt.ls-java-project
                 │    ├─ importProjects() OR importProjectsFromConfigurationFiles()  — 70% of monitor
                 │    │    └─ FOR EACH rootPath (sequential!):
                 │    │         └─ FOR EACH importer (ordered by priority):
                 │    │              ├─ importer.initialize(rootFolder)
                 │    │              ├─ importer.applies()          — scan filesystem for build files
                 │    │              ├─ importer.importToWorkspace() — DO THE IMPORT
                 │    │              └─ importer.isResolved()? → break
                 │    ├─ updateEncoding()                           — set project charset
                 │    └─ reportProjectsStatus()                     — send diagnostics
                 ├─ projectsManager.configureFilters()              — set resource filters
                 ├─ connection.sendStatus(Started, "Ready")
                 └─ (finally) projectsManager.registerListeners()
                      ├─ configureSettings()                       — apply formatter/settings
                      ├─ add preferenceChangeListener
                      └─ buildSupports().forEach(registerPreferencesChangeListener)
```

### 4.2 — Importer Priority Order and Behavior

Importers are loaded from the `org.eclipse.jdt.ls.core.importers` extension point and executed in **order** priority. The default order is:

| Order | Importer | Applies when | What it does |
|-------|----------|-------------|--------------|
| 0 | `GradleProjectImporter` | `build.gradle` / `settings.gradle(.kts)` found | Scans dirs → for each dir: `startSynchronization()` calls Buildship `gradleBuild.synchronize()` |
| 100 | `MavenProjectImporter` | `pom.xml` found | Scans dirs → `configurationManager.importProjects()` (m2e) → `updateProjects()` |
| 200 | `EclipseProjectImporter` | `.project` file found | Open existing Eclipse projects |
| 1000 | `InvisibleProjectImporter` | No visible projects found | Create an "invisible" project for unmanaged Java files |

**Key detail:** For the old-style `importProjects()` path, once an importer's `isResolved()` returns true for a root path, the importer loop **breaks** — so a Gradle project won't also be imported by Maven. For the new `importProjectsFromConfigurationFiles()` path, all applicable importers run and resolved configs are removed from the running set.

### 4.3 — Where Time Is Actually Spent

Based on code analysis, the time-consuming phases during initialization are:

#### Phase A: `waitForRepositoryRegistryUpdateJob()` (blocking, up to 300s)
- **Where:** `InitHandler.triggerInitialization()` L262
- **What:** Blocks the initialization job until the Maven repository index update completes. This is an Eclipse/m2e background job that indexes the local Maven repository (`~/.m2/repository`).
- **Impact:** For a large local Maven cache (thousands of artifacts), this can take 10-30+ seconds. The initialization **cannot proceed** until this finishes.
- **Code:** `JobHelpers.waitForJobs(RepositoryRegistryUpdateJobMatcher.INSTANCE, MAX_TIME_MILLIS)` where `MAX_TIME_MILLIS = 300000` (5 minutes!)

#### Phase B1: `applies()` — Filesystem Scanning
- **Where:** Each importer's `applies()` method
- **What:** `BasicFileDetector` walks the entire project tree (up to depth 5) looking for build files (`pom.xml`, `build.gradle`, etc.)
- **Performance characteristics:**
  - Uses `Files.walkFileTree()` with `FOLLOW_LINKS` option
  - Applies exclusion patterns via glob matching on every directory visited
  - For each project already in workspace, adds its path as an exclusion (building exclusion set is O(existingProjects))
  - **For a project with deep nested directories, this walk can be slow** — thousands of directories to visit
- **Code:** `BasicFileDetector.scan()` → `scanDir()` → `Files.walkFileTree(dir, FOLLOW_LINKS_OPTION, maxDepth, visitor)`

#### Phase B2: Gradle — `startSynchronization()` (MOST EXPENSIVE)
- **Where:** `GradleProjectImporter.importToWorkspace()` L248 → `importDir()` → `startSynchronization()`
- **What:** For each Gradle project directory, calls `gradleBuild.synchronize(monitor)` which:
  1. Launches/connects to the Gradle daemon
  2. Resolves the Gradle model (downloads dependencies if needed)
  3. Generates `.classpath`, `.project`, `.settings/` files
  4. Imports/configures Eclipse projects from the model
- **Critical bottleneck:** Each directory is imported **sequentially** (L248 loop). If you have N independent Gradle builds, they run one after another. Even within a single multi-module Gradle build, the `synchronize()` call blocks until the entire model is resolved.
- **After sync:** Digest store is updated for each project's build files (L257-269), annotation processing is synced if needed (L325-331).
- **`shouldSynchronize()` check (L582-619):** Before syncing, checks if the Gradle model persistence file is older than the build files. On first import, always syncs. On re-import, only syncs if build files changed — this is a useful optimization that works correctly.

#### Phase B3: Maven — `configurationManager.importProjects()` + `updateProjects()`
- **Where:** `MavenProjectImporter.importToWorkspace()` L160-248
- **What:**
  1. `collectMavenProjectInfo()` — Uses m2e's `LocalProjectScanner` to parse all POM files and build the project dependency tree. This resolves parent POMs recursively.
  2. Separates projects into "toImport" (new) and "projects" (existing, need update)
  3. For large projects (> `MAX_PROJECTS_TO_IMPORT=50` when low memory), imports in **chunks** to avoid OOM
  4. `updateProjects()` — For each existing project: opens it, refreshes it, then schedules `MavenBuildSupport.update()` as a `WorkspaceJob`
  5. `MavenBuildSupport.update()` calls `configurationManager.updateProjectConfiguration()` which resolves the Maven model, downloads dependencies, and configures classpaths
- **Critical bottleneck:** `configurationManager.importProjects()` is the m2e API call. For hundreds of Maven modules, this resolves ALL transitive dependencies and generates `.classpath` files. This is CPU+network bound.
- **The `updateProjects()` is also expensive:** It's scheduled as a separate `WorkspaceJob` that runs `MavenBuildSupport.update()` for each project. `collectProjects()` recurses through the Maven module hierarchy to find all affected projects.

#### Phase B4: Eclipse Import — `importDir()`
- **Where:** `EclipseProjectImporter.importToWorkspace()` L102-111
- **What:** For each `.project` directory, load the project descriptor and open it. Relatively fast — just workspace metadata operations.
- **Impact:** Low. This is I/O bound but typically fast.

#### Phase B5: Invisible Project — `loadInvisibleProject()`
- **Where:** `InvisibleProjectImporter.importToWorkspace()` L85-113
- **What:** Only runs if no visible projects were found. Creates a default Java project and configures classpath from trigger files.
- **Impact:** Low. Only applies to unmanaged workspaces.

#### Phase C: Post-Import Work
After `initializeProjects()` returns, the following happens:
1. **`configureFilters()`** — Applies resource filters to all projects. O(projects × filters).
2. **`registerListeners()`** — Sets up preference change listeners and registers build support listeners. Calls `buildSupports()` which (without Step 1.1 fix) re-instantiates all build supports.
3. **`registerWatcherJob`** — Scheduled to run after `JobHelpers.waitForJobsToComplete()` — this itself waits for ALL workspace jobs to finish, then computes file watchers (O(projects × classpath entries)).
4. **Auto-build resumes** — The `resetBuildState` runnable re-enables auto-build, which triggers a full workspace build. This is when:
   - Java compiler runs on all source files
   - `.class` files are generated
   - Search indexes are built (`checkIndexes()` in `projectsBuildFinished()`)
   - `projectsImported()` triggers Protobuf/Android framework support
   - `projectsBuildFinished()` triggers `compile()` on all build supports (Gradle Groovy/Kotlin compilation)

### 4.4 — Key Bottleneck Summary (Ranked by Impact)

| Rank | Bottleneck | Phase | Typical Time | Why It's Slow |
|------|-----------|-------|-------------|---------------|
| 1 | **Gradle `synchronize()`** | B2 | 30s-5min per build | Launches Gradle daemon, resolves entire dependency tree, generates Eclipse metadata. Sequential per directory. |
| 2 | **Maven `importProjects()`** | B3 | 20s-3min | m2e resolves all POM dependencies, downloads artifacts, configures classpaths for all modules. |
| 3 | **Auto-build after import** | C | 30s-2min | Full Java compilation + index building for all imported projects. |
| 4 | **`waitForRepositoryRegistryUpdateJob()`** | A | 5-30s | Blocks on Maven repo index. Large `~/.m2/repository` = long wait. |
| 5 | **`BasicFileDetector.scan()`** | B1 | 1-10s | Walks entire directory tree up to depth 5 with glob matching. |
| 6 | **`registerWatchers()`** | C | 1-5s | O(projects × classpath entries) computation + waits for all jobs to complete first. |
| 7 | **Maven `updateProjects()`** | B3 | 5-30s | Per-project Maven model resolution for existing projects. |

### 4.5 — Potential Improvements for Project Initialization

#### 4.5.1 — Parallel Gradle Synchronization for Independent Builds (Step 3.3 Enhancement)
Independent Gradle builds (separate `settings.gradle` roots) can safely be synchronized in parallel since they use different Gradle daemons. The current sequential loop in `GradleProjectImporter.importToWorkspace()` L248 is the single biggest bottleneck for workspaces with multiple Gradle builds.

#### 4.5.2 — Skip `waitForRepositoryRegistryUpdateJob()` or Make It Non-Blocking
The 300-second timeout on waiting for Maven repository indexing is excessive. Options:
- Make it non-blocking: start import immediately, let the index job run in parallel
- Reduce timeout to a reasonable value (e.g., 30s)
- Skip entirely if the workspace hasn't changed (digest check)

#### 4.5.3 — Cache `BasicFileDetector` Scan Results
The filesystem scan results could be cached across restarts (similar to DigestStore). If the root paths haven't changed and no new build files were added, reuse the previous scan results. Invalidate on workspace folder changes.

#### 4.5.4 — Defer Auto-Build Until Needed
Instead of resuming auto-build immediately after import (which triggers full compilation), defer it until the first user interaction that requires compiled code (e.g., diagnostics request, completion). This would make the "Ready" status appear faster, with compilation happening lazily.

#### 4.5.5 — Incremental Maven Import
For Maven projects that were previously imported and haven't changed their `pom.xml`, skip the `updateProjectConfiguration()` call entirely. The current `needsMavenUpdate()` check compares `pom.xml` timestamp to `lastWorkspaceStateSaved`, but this timestamp is coarse — it could use DigestStore for precise change detection.

---

## Section 5: GradleBuildServerProjectImporter Analysis (vscode-gradle extension)

### 5.1 — Discovery: The Real Bottleneck Is NOT in eclipse.jdt.ls

**Key finding from real-world testing (spring-boot project, 12+ min init):**

The importer that actually handles Gradle projects is `GradleBuildServerProjectImporter` from the **vscode-gradle** extension (`com.microsoft.gradle.bs.importer-0.5.4.jar`), NOT the `GradleProjectImporter` in eclipse.jdt.ls. The priority order is:

| Priority | Importer | Source |
|----------|----------|--------|
| — | `PDEProjectImporter` | eclipse.jdt.ls |
| — | **`GradleBuildServerProjectImporter`** | **vscode-gradle extension** |
| 0 | `GradleProjectImporter` | eclipse.jdt.ls |
| 100 | `MavenProjectImporter` | eclipse.jdt.ls |

Because `GradleBuildServerProjectImporter` resolves the project, `GradleProjectImporter.importToWorkspace()` is **never called**. All Section 4 improvements targeting `GradleProjectImporter` are irrelevant when the build server importer is active (default when `java.gradle.buildServer.enabled` is `"on"`).

**Repo:** [microsoft/vscode-gradle](https://github.com/microsoft/vscode-gradle)
**Source:** `extension/jdtls.ext/com.microsoft.gradle.bs.importer/src/com/microsoft/gradle/bs/importer/`

### 5.2 — GradleBuildServerProjectImporter Full Flow

```
GradleBuildServerProjectImporter.importToWorkspace()
├── Determine inferredRoot from directories (sorted by depth)
├── ImporterPlugin.getBuildServerConnection(rootPath, true)
│     └── Connect to Gradle Build Server via NamedPipe (started by vscode-gradle TS extension)
├── [BLOCKING] buildServer.buildInitialize(params).join()          ← BOTTLENECK #1
│     └── Gradle Build Server starts Gradle daemon, resolves ALL configurations
├── buildServer.onBuildInitialized()
├── importProjects(buildServer, monitor)
│     ├── [BLOCKING] Utils.getBuildTargetsMappedByProjectPath(buildServer)
│     │     └── serverConnection.workspaceBuildTargets().join()    ← BSP call #1
│     └── FOR EACH project URI in buildTargetMap:
│           ├── createProject() or updateProjectDescription()
│           └── project.refreshLocal()
├── FOR EACH project (sequential):                                ← BOTTLENECK #2
│     └── buildSupport.updateClasspath(buildServer, project, monitor)
│           ├── Utils.getBuildTargetsByProjectUri(connection, ...)
│           │     └── serverConnection.workspaceBuildTargets().join()  ← REDUNDANT BSP call
│           ├── FOR EACH build target (sequential):               ← BOTTLENECK #3
│           │     ├── connection.buildTargetOutputPaths([target]).join()
│           │     ├── connection.buildTargetSources([target]).join()
│           │     └── connection.buildTargetResources([target]).join()
│           ├── FOR EACH build target (sequential):
│           │     └── connection.buildTargetDependencyModules([target]).join()
│           └── connection.buildTargetJavacOptions(allTargets).join()
├── FOR EACH project (sequential):
│     └── buildSupport.updateProjectDependencies(buildServer, project, monitor)
│           └── Utils.getBuildTargetsByProjectUri(connection, ...)
│                 └── serverConnection.workspaceBuildTargets().join()  ← REDUNDANT BSP call
└── FOR EACH project:
      └── updateConfigurationDigest(project)
```

### 5.3 — Identified Bottlenecks

#### Bottleneck #1: `buildServer.buildInitialize().join()` — The Dominant Cost
- **Impact:** ~90%+ of total init time (likely the entire 12 minutes for spring-boot)
- **What happens:** The Gradle Build Server launches the Gradle daemon, which resolves all project configurations, downloads dependencies, evaluates all `build.gradle` files, and discovers all source sets/targets.
- **Why it's slow:** For spring-boot (400+ subprojects), evaluating all Gradle build scripts and resolving all dependency configurations is inherently expensive.
- **Optimization:** This is Gradle execution time. Can be improved via Gradle flags:
  - `--parallel` — Resolves subproject configurations in parallel (Gradle-level parallelism)
  - `--configuration-cache` — Skips re-evaluation of build scripts on subsequent imports if inputs haven't changed (<ins>**massive** potential speedup on re-import</ins>)
  - These flags are passed via `BuildServerPreferences.gradleArguments` ← `java.import.gradle.arguments` VS Code setting

#### Bottleneck #2: Sequential `updateClasspath()` Per Project
- **Impact:** Medium — O(projects) sequential BSP round-trips
- **What happens:** For each project, `updateClasspath()` makes multiple blocking BSP calls. With 400+ projects, even if each call is fast (10-50ms), the sequential overhead is 400× the latency.
- **Optimization:** Parallelize `updateClasspath()` across projects (they are independent).

#### Bottleneck #3: Per-Target Sequential BSP Calls in `updateClasspath()`
- **Impact:** Medium — For each project, N BSP calls where N = number of build targets (source sets)
- **What happens:** BSP APIs (`buildTargetOutputPaths`, `buildTargetSources`, `buildTargetResources`, `buildTargetDependencyModules`) accept a **list** of target IDs but are called with `Arrays.asList(buildTarget.getId())` — i.e., **one target at a time**. This means:
  - If a project has 2 source sets (main + test), that's 2×3 = 6 sequential BSP calls just for sources/outputs/resources, then 2 more for dependency modules.
  - The BSP protocol is designed for bulk queries, but this code doesn't use that capability.
- **Optimization:** Batch all build targets into a single BSP call per method:
  ```java
  // BEFORE: N sequential calls
  for (BuildTarget buildTarget : buildTargets) {
      OutputPathsResult outputResult = connection.buildTargetOutputPaths(
          new OutputPathsParams(Arrays.asList(buildTarget.getId()))).join();
  }
  // AFTER: 1 batched call
  List<BuildTargetIdentifier> allIds = buildTargets.stream()
      .map(BuildTarget::getId).collect(Collectors.toList());
  OutputPathsResult outputResult = connection.buildTargetOutputPaths(
      new OutputPathsParams(allIds)).join();
  ```

#### Bottleneck #4: Redundant `workspaceBuildTargets()` Calls
- **Impact:** Low-Medium — O(2N+1) identical BSP calls
- **What happens:**
  - Called once in `importProjects()` via `getBuildTargetsMappedByProjectPath()`
  - Called again **per project** in `updateClasspath()` via `getBuildTargetsByProjectUri()`
  - Called again **per project** in `updateProjectDependencies()` via `getBuildTargetsByProjectUri()`
  - Total: 1 + N + N = 2N+1 calls for N projects, all returning the same data
- **Optimization:** Cache the result of `workspaceBuildTargets()` at the start and pass it to all consumers.

### 5.4 — Proposed Improvements (vscode-gradle repo)

#### 5.4.1 — Immediate: Gradle Flags via User Settings (No Code Change)
Add to VS Code `settings.json`:
```json
{
  "java.import.gradle.arguments": "--parallel --configuration-cache"
}
```
- `--parallel`: Gradle resolves subproject configurations in parallel during build initialization
- `--configuration-cache`: On re-import, Gradle skips build script evaluation entirely if inputs haven't changed (can reduce 12min → seconds on second+ import)
- **Caveat:** `--configuration-cache` may fail on first use for some builds; some plugins don't support it yet

#### 5.4.2 — Cache `workspaceBuildTargets()` Result
**File:** `GradleBuildServerProjectImporter.java` → `importToWorkspace()`
**Change:** Call `workspaceBuildTargets().join()` once, cache the result, and pass it to `updateClasspath()` and `updateProjectDependencies()`.
**Savings:** 2N network/IPC round-trips eliminated for N projects.

#### 5.4.3 — Batch BSP Calls in `updateClasspath()`
**File:** `GradleBuildServerBuildSupport.java` → `updateClasspath()`
**Change:** Instead of calling `buildTargetOutputPaths`, `buildTargetSources`, `buildTargetResources`, `buildTargetDependencyModules` once per target, batch all targets into single calls:
1. One `buildTargetOutputPaths()` call with all target IDs
2. One `buildTargetSources()` call with all target IDs
3. One `buildTargetResources()` call with all target IDs
4. One `buildTargetDependencyModules()` call with all target IDs
5. Already done: `buildTargetJavacOptions()` with all targets

**Savings:** Reduces 4N BSP calls to 4 total per project. For 2 source sets per project × 400 projects, that's ~3200 → ~1600 BSP calls eliminated.

#### 5.4.4 — Parallelize `updateClasspath()` Across Projects
**File:** `GradleBuildServerProjectImporter.java` → `importToWorkspace()`
**Change:** Use a thread pool to run `updateClasspath()` for independent projects in parallel.
**Savings:** With 400 projects and 8 threads, ~8× faster classpath update phase.
**Risk:** Must verify `IJavaProject.setRawClasspath()` is thread-safe across different projects.

### 5.5 — Impact Estimate

| Step | Where | Expected Impact | Effort |
|------|-------|----------------|--------|
| 5.4.1 `--parallel` | User setting | 10-40% faster `buildInitialize` | None (config only) |
| 5.4.1 `--configuration-cache` | User setting | **80-95% faster re-import** | None (config only) |
| 5.4.2 Cache build targets | vscode-gradle | Eliminate 2N BSP round-trips | Small |
| 5.4.3 Batch BSP calls | vscode-gradle | Eliminate ~4N BSP calls per project | Medium |
| 5.4.4 Parallel classpath | vscode-gradle | ~8× faster classpath phase | Medium-High |

**Key insight:** Step 5.4.1 (`--configuration-cache`) is likely the single highest-impact change for repeat imports, and it requires zero code changes — just a user setting.

---

## Excluded from scope
- Changes to m2e or Buildship internals (external dependencies)
- Parallel Maven chunk imports (m2e's `importProjects` may not be thread-safe)
- Changes to `initializeProjects()` root path parallelism (requires deep understanding of workspace locking)
- Changes to the Gradle Build Server process itself (the `gradle-server` component in vscode-gradle that handles BSP protocol server-side)
