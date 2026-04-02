# Performance Analysis: Java Projects View Loading for Spring Boot

## Executive Summary

Loading the [spring-boot](https://github.com/spring-projects/spring-boot) project (400+ Gradle subprojects) takes **702 seconds (~11.7 minutes)** before the "Java Projects" tree view shows any content. The entire pipeline — from LSP `initialize` to the tree view populating — is **completely serial**, with no progressive feedback and no parallelism at any layer.

This document analyzes every stage of the pipeline using the LSP log and source code, identifies bottlenecks, and proposes concrete improvements.

---

## Timeline Analysis (from `lsp.log`)

| Time | Event | Duration |
|------|-------|----------|
| 10:16:37.772 | Session start | — |
| 10:16:40.370 | `JavaLanguageServerPlugin` started | 2.6s (JVM startup) |
| 10:16:40.856 | `>> initialize` received | — |
| 10:16:41.435 | `ProjectRegistryRefreshJob` finished | 919ms |
| 10:16:42.206–42.298 | JVM runtimes configured (5 JDKs) | 0.1s |
| 10:16:42.342–42.842 | **60+ plugin JARs installed** | 0.5s |
| 10:16:42.842–43.153 | Bundle refresh | 0.3s |
| 10:16:43.154–43.222 | Bundles started + commands registered | 0.07s |
| 10:16:43.284 | Importers listed, **import begins** | — |
| **10:16:43 → 10:28:25** | **`Workspace initialized in 702045ms`** | **702s (11.7 min)** |
| 10:28:26.716 | Build jobs finished | 1.4s |
| 10:28:26.841 | `registerWatchers` | — |

**Key Finding**: 99.4% of the total time (702s out of 706s) is spent in `initializeProjects()`, specifically in the Gradle Build Server import.

---

## Architecture: End-to-End Flow

```
User opens spring-boot project
  ↓
vscode-java activates → spawns eclipse.jdt.ls (JVM startup: ~2.6s)
  ↓
LSP initialize → InitHandler.triggerInitialization()
  ↓
WorkspaceJob "Initialize Workspace"
  ├─ waitForRepositoryRegistryUpdateJob()           [~1s]
  ├─ projectsManager.initializeProjects(roots)      [~702s ★★★]
  │   ├─ cleanInvalidProjects()
  │   └─ importProjects() ← sequential importers:
  │       └─ GradleBuildServerProjectImporter.importToWorkspace()
  │           ├─ buildServer.buildInitialize().join()  [BLOCKS: Gradle daemon + all build.gradle eval]
  │           ├─ importProjects() via BSP              [N+1 workspaceBuildTargets calls]
  │           ├─ updateClasspath() per project         [4N per-target sequential BSP calls]
  │           ├─ updateProjectDependencies()           [N+1 workspaceBuildTargets calls again]
  │           └─ updateConfigurationDigest()           [serialize per file]
  ├─ configureFilters()
  └─ connection.sendStatus(Started, "Ready")  ← ONLY NOW server is "ready"
  ↓
vscode-java-dependency: languageServerApiManager.ready()  ← was waiting for "Ready"
  ↓
DependencyDataProvider.getChildren() → Jdtls.getProjectList()
  ↓
java.project.list → ProjectCommand.listProjects()  ← returns all 400+ projects
  ↓
Tree view finally renders
```

---

## Bottleneck Analysis

### Bottleneck #1: Gradle Build Server Initialization (est. ~80-90% of 702s)
**Location**: `GradleBuildServerProjectImporter.java` L210-212
```java
InitializeBuildResult initializeResult = buildServer.buildInitialize(params).join();
buildServer.onBuildInitialized();
```
**Root Cause**: `buildInitialize().join()` blocks while the Gradle Build Server:
1. Spawns a Gradle daemon (cold start: 5-15s)
2. Evaluates **every** `build.gradle` / `settings.gradle.kts` file (400+ in spring-boot)
3. Resolves **all** dependency configurations (downloading metadata, computing dependency graphs)
4. Discovers all build targets (source sets)

**Impact**: This is a single synchronous blocking call for the entire project tree. No work can proceed until it completes.

### Bottleneck #2: Per-Target Sequential BSP Calls (est. ~5-15% of 702s)
**Location**: `GradleBuildServerBuildSupport.java` L226-264
```java
for (BuildTarget buildTarget : buildTargets) {
    connection.buildTargetOutputPaths(...).join();   // blocking
    connection.buildTargetSources(...).join();        // blocking
    connection.buildTargetResources(...).join();      // blocking
    // ...
    connection.buildTargetDependencyModules(...).join(); // blocking
}
```
**Root Cause**: For each of the ~800 build targets (400 projects × ~2 source sets each), **4 sequential blocking RPC calls** are made. Only `javacOptions` is batched.

**Math**: 800 targets × 4 calls × ~5ms round-trip = **16 seconds** minimum. With Gradle daemon contention, likely **30-90 seconds**.

### Bottleneck #3: Redundant `workspaceBuildTargets()` Calls
**Location**: `Utils.java` L55 and L71
```java
// Called N+1 times: once in importProjects(), once per project in updateClasspath()
WorkspaceBuildTargetsResult result = serverConnection.workspaceBuildTargets().join();
```
**Root Cause**: `getBuildTargetsByProjectUri()` and `getBuildTargetsMappedByProjectPath()` both call `workspaceBuildTargets().join()` independently. For 400 projects, this means **401** full workspace queries that return all targets, then filter. Additionally, `updateProjectDependencies()` calls `getBuildTargetsByProjectUri()` again per project, adding another 400 calls. **Total: ~801 calls** when 1 would suffice.

### Bottleneck #4: DigestStore Serialization Thrashing
**Location**: `GradleBuildServerProjectImporter.java` L262-283
```java
for (IProject project : projects) {
    updateConfigurationDigest(project);  // up to 4 digestStore.updateDigest() per project
    // Each updateDigest() serializes the ENTIRE HashMap via ObjectOutputStream
}
```
**Root Cause**: For 400 projects × up to 4 config files = **~1600 full serializations** of the same HashMap.

### Bottleneck #5: Tree View Blocked Until Full Completion
**Location**: `languageServerApiManager.ts` L31
```typescript
await this.extensionApi.serverReady();  // waits for JDTLS "Ready" status
```
**Root Cause**: The Java Projects tree view calls `languageServerApiManager.ready()` which blocks on `extensionApi.serverReady()`. This promise only resolves when `InitHandler` calls `connection.sendStatus(ServiceStatus.Started, "Ready")` — **after ALL projects are fully imported**. The user sees an empty tree for the entire 702 seconds.

### Bottleneck #6: Sequential Project Classpath Updates
**Location**: `GradleBuildServerProjectImporter.java` L230-233
```java
for (IProject project : projects) {
    buildSupport.updateClasspath(buildServer, project, monitor);  // sequential
}
```
**Root Cause**: Each project's classpath is updated one at a time. The BSP calls within each `updateClasspath()` are also sequential. No overlap between projects.

---

## Improvement Proposals

### Proposal 1: Progressive / Incremental Project Loading (High Impact — UX Change) ✅ IMPLEMENTED

**Problem**: Users see an empty Java Projects tree for 11.7 minutes.

**Solution**: A 3-layer change across `eclipse.jdt.ls`, `vscode-java`, and `vscode-java-dependency` that enables the tree view to show project names progressively during import — without querying the blocked JDTLS server.

**Result**: All 436 project names appear in the tree view within ~2 seconds of import starting, instead of waiting 702s. Expanding projects still requires the server (blocked until import completes for that project's classpath setup).

#### Layer 1: Server-Side Progressive Notifications (`eclipse.jdt.ls`)

**File**: `ProjectsManager.java` — `importProjects()`

A `ScheduledExecutorService` polls every 2 seconds during the import loop. It checks `getWorkspaceRoot().getProjects()` for newly accessible projects and sends a `language/eventNotification` with `EventType.ProjectsImported` containing the new project URIs. A `ConcurrentHashMap.newKeySet()` tracks already-notified projects to avoid duplicates. A final flush in the `finally` block catches any remaining projects after importers complete.

**File**: `JDTLanguageServer.java` — `executeCommand()`

Added `INDEX_INDEPENDENT_COMMANDS` set (`java.project.list`, `java.project.checkImportStatus`, `java.getPackageData`, `java.resolvePath`, `java.project.getAll`) that skip `waitForIndex()`. This allows tree view queries to reach the delegate command handler without waiting for the search index. (Note: during import, Eclipse workspace locks still block these queries — this unblocks them for the *post-import* phase before indexing completes.)

#### Layer 2: Early Server Running API (`vscode-java`)

**File**: `extension.api.ts`

Bumped `extensionApiVersion` to `'0.14'`. Added `serverRunning?: () => Promise<boolean>` to the `ExtensionAPI` interface.

**File**: `apiManager.ts`

Added `serverRunningPromise` / `serverRunningPromiseResolve` fields. The `serverRunning()` API resolves on the *first* `StatusNotification` from the server (indicating the JVM process is alive), much earlier than `serverReady()` which waits for full import completion.

**File**: `standardLanguageClient.ts`

Calls `apiManager.resolveServerRunningPromise()` at the top of the `StatusNotification.type` handler, before the switch statement.

#### Layer 3: Client-Side Progressive Rendering (`vscode-java-dependency`)

This is the **key innovation**: the tree view creates `ProjectNode` items directly from the notification URIs, completely bypassing the blocked JDTLS server.

**File**: `commands.ts`

Added `VIEW_PACKAGE_INTERNAL_ADD_PROJECTS` command constant.

**File**: `dependencyDataProvider.ts`

- **`addProgressiveProjects(projectUris: string[])`**: New method that creates `ProjectNode` items from URIs without any server query. Extracts the project name from the URI's last path segment, deduplicates against existing items, and fires `_onDidChangeTreeData` to update the tree.
- **`getChildren()` fast path**: When `_rootItems` is already populated by progressive loading, returns them immediately without calling `languageServerApiManager.ready()` or `getRootNodes()` (both of which would block on server queries).
- **`VIEW_PACKAGE_INTERNAL_ADD_PROJECTS` command**: Registered in the constructor, routing to `addProgressiveProjects()`.

**File**: `languageServerApiManager.ts`

- **`ready()`**: Uses `serverRunning()` (API >= 0.14) instead of `serverReady()`. Also starts a background `serverReady().then(...)` listener that triggers a full `VIEW_PACKAGE_INTERNAL_REFRESH` when import completes — replacing progressive placeholder items with full data from the server.
- **`onDidProjectsImport` handler**: Calls `VIEW_PACKAGE_INTERNAL_ADD_PROJECTS` with the notification URIs instead of `VIEW_PACKAGE_INTERNAL_REFRESH`. This adds projects to the tree without querying the server.
- **`onDidClasspathUpdate` handler**: During import (`!isServerReady`), routes to `VIEW_PACKAGE_INTERNAL_ADD_PROJECTS` (no-op if project already in tree). After import (`isServerReady`), does a normal `VIEW_PACKAGE_INTERNAL_REFRESH`.

#### Key Design Insight

The original approach tried to trigger `refresh()` on each notification, which calls `getChildren()` → `getRootNodes()` → `Jdtls.checkImportStatus()` → server query → **blocked by Eclipse workspace locks**. The server literally cannot respond to any `workspace/executeCommand` request while the Gradle BSP importer holds workspace locks for `project.create()`, `project.open()`, `refreshLocal()`, `updateClasspath()`, etc.

The solution decouples the tree view's initial rendering from the server entirely. The `ProjectsImported` notification carries the URIs needed to display project names. The server is only queried once import finishes (via the background `serverReady()` listener) to replace placeholders with full data.

#### Current Limitation

Expanding a project node calls `ProjectNode.loadData()` → `Jdtls.getPackageData()` → server query, which is still blocked during import. This is acceptable because:
1. Users can see and scroll the full project list immediately
2. The status bar shows import progress
3. Projects become expandable as their classpath setup completes

#### 1B: Streaming Project Import (BSP-Level) — NOT IMPLEMENTED

**Problem**: `buildInitialize()` is all-or-nothing.

**Solution**: In the Gradle Build Server (`build-server-for-gradle`), emit `build/taskProgress` notifications as each subproject is evaluated. On the JDTLS side, use these progress events to create projects incrementally.

**Changes**:
- **`build-server-for-gradle`**: Emit BSP `build/taskProgress` notifications with project URIs as they become available during initialization.
- **`GradleBuildServerProjectImporter.java`**: Register a `GradleBuildClient` callback for `onBuildTaskProgress` that creates IProject objects as they arrive.
- **`GradleBuildServerBuildSupport.java`**: Trigger classpath updates per-project as their build targets become available.

**Estimated Impact**: Projects appear in tree view in seconds, full classpath available progressively.

---

### Proposal 2: Batch BSP Calls (High Impact — Moderate Effort)

**Problem**: 4N sequential blocking BSP calls for N build targets.

**Solution**: BSP `buildTarget/*` APIs accept a *list* of `BuildTargetIdentifier`. Batch all targets into a single call per operation.

**Changes in `GradleBuildServerBuildSupport.java`**:

```java
// BEFORE (per-target, 4N calls):
for (BuildTarget bt : buildTargets) {
    connection.buildTargetOutputPaths(new OutputPathsParams(List.of(bt.getId()))).join();
    connection.buildTargetSources(new SourcesParams(List.of(bt.getId()))).join();
    // ...
}

// AFTER (batched, 4 calls total):
List<BuildTargetIdentifier> allIds = buildTargets.stream()
    .map(BuildTarget::getId).collect(Collectors.toList());
OutputPathsResult allOutputs = connection.buildTargetOutputPaths(new OutputPathsParams(allIds)).join();
SourcesResult allSources = connection.buildTargetSources(new SourcesParams(allIds)).join();
ResourcesResult allResources = connection.buildTargetResources(new ResourcesParams(allIds)).join();
DependencyModulesResult allDeps = connection.buildTargetDependencyModules(
    new DependencyModulesParams(allIds)).join();
// Then map results back to per-target processing
```

**Also batch across projects**: Instead of calling `updateClasspath()` per project (each making its own BSP calls), collect all build target IDs from all projects, make one batch call, and distribute results.

**Estimated Impact**: Reduce ~3200 BSP round-trips to ~4 total. Potential saving: **30-90 seconds**.

---

### Proposal 3: Cache `workspaceBuildTargets()` Result (High Impact — Easy)

**Problem**: `workspaceBuildTargets()` called ~801 times when 1 suffices.

**Solution**: Cache the result after the first call per import cycle.

**Changes in `GradleBuildServerProjectImporter.java`**:

```java
// In importToWorkspace(), after buildInitialize():
WorkspaceBuildTargetsResult cachedTargets = buildServer.workspaceBuildTargets().join();

// Pass to importProjects and updateClasspath:
List<IProject> projects = importProjects(cachedTargets, monitor);
for (IProject project : projects) {
    buildSupport.updateClasspath(connection, project, cachedTargets, monitor);
}
```

**Changes in `Utils.java`**: Add overloads that accept pre-fetched `WorkspaceBuildTargetsResult`:
```java
public static Map<URI, List<BuildTarget>> getBuildTargetsMappedByProjectPath(
        WorkspaceBuildTargetsResult result) {
    return result.getTargets().stream()
        .collect(Collectors.groupingBy(t -> getUriWithoutQuery(t.getId().getUri())));
}

public static List<BuildTarget> getBuildTargetsByProjectUri(
        WorkspaceBuildTargetsResult result, URI projectUri) {
    return result.getTargets().stream()
        .filter(t -> URIUtil.sameURI(projectUri, getUriWithoutQuery(t.getId().getUri())))
        .collect(Collectors.toList());
}
```

**Estimated Impact**: Eliminate ~800 redundant RPC round-trips. Potential saving: **4-10 seconds** + reduced Gradle daemon load.

---

### Proposal 4: Parallel Project Classpath Updates (Medium Impact — Moderate Effort)

**Problem**: Classpath updates are serial across 400 projects.

**Solution**: Use a bounded thread pool to update classpaths in parallel (BSP server can handle concurrent requests).

**Changes in `GradleBuildServerProjectImporter.java`**:

```java
// BEFORE:
for (IProject project : projects) {
    buildSupport.updateClasspath(buildServer, project, monitor);
}

// AFTER:
int parallelism = Math.min(Runtime.getRuntime().availableProcessors(), 8);
ExecutorService executor = Executors.newFixedThreadPool(parallelism);
List<CompletableFuture<Void>> futures = projects.stream()
    .map(project -> CompletableFuture.runAsync(() -> {
        try {
            buildSupport.updateClasspath(buildServer, project, monitor);
        } catch (CoreException e) {
            JavaLanguageServerPlugin.logException("Failed to update classpath", e);
        }
    }, executor))
    .collect(Collectors.toList());
CompletableFuture.allOf(futures.toArray(new CompletableFuture[0])).join();
executor.shutdown();
```

**Risk**: Need to verify BSP server handles concurrent requests safely. The `setRawClasspath()` calls in JDT may need workspace locks.

**Estimated Impact**: Potential 3-8× speedup for the classpath update phase.

---

### Proposal 5: Batch DigestStore Serialization (Medium Impact — Easy)

**Problem**: ~1600 full HashMap serializations during import.

**Solution**: Defer serialization until the end of import.

**Changes**: Already documented in the existing `CLASSPATH_PERF_PLAN.md` (Step 1.2). Implement:
- Add `dirty` flag to `DigestStore`
- Add `flush()` method
- Add `updateDigests(Collection<Path>)` batch method
- Call `flush()` once at end of `importToWorkspace()`

**Estimated Impact**: Eliminate serialization overhead. Potential saving: **2-5 seconds** for 400 projects.

---

### Proposal 6: Deferred / Lazy Tree View Population (Medium Impact — UX)

**Problem**: Tree view calls `java.project.list` which returns ALL 400+ projects at once.

**Solution**: Implement pagination or progressive loading in the tree.

#### 6A: Workspace-Level Grouping
- Group projects by top-level module directory
- Load child projects only on expand
- Already partially implemented via `WorkspaceNode` → `ProjectNode` hierarchy

#### 6B: Paginated `java.project.list`
**Changes in `ProjectCommand.java`**:
```java
// Add optional pagination parameters:
// arguments[2]: offset (int)
// arguments[3]: limit (int)
public static List<PackageNode> listProjects(List<Object> arguments, IProgressMonitor monitor) {
    // ... existing logic ...
    int offset = arguments.size() > 2 ? ((Number) arguments.get(2)).intValue() : 0;
    int limit = arguments.size() > 3 ? ((Number) arguments.get(3)).intValue() : Integer.MAX_VALUE;
    return results.stream().skip(offset).limit(limit).collect(Collectors.toList());
}
```

**Estimated Impact**: Reduces initial tree render time from showing all 400 projects to showing first batch instantly.

---

### Proposal 7: Build Server Pre-warming (Medium Impact — Easy)

**Problem**: Gradle daemon cold-start adds 5-15 seconds.

**Solution**: Start the Gradle Build Server connection and daemon warm-up earlier, during the LSP initialization phase rather than waiting for importers to run.

**Changes**:
- **`vscode-gradle`**: On activation, if Gradle files are detected, immediately start the build server process and initiate connection (without `buildInitialize`).
- **`GradleBuildServerProjectImporter.java`**: In `applies()`, start the connection asynchronously so it's ready by the time `importToWorkspace()` is called.

**Estimated Impact**: Save 5-15 seconds of daemon cold-start.

---

### Proposal 8: Gradle Configuration Cache Support (High Impact — Configuration)

**Problem**: Every open re-evaluates all `build.gradle` files from scratch.

**Solution**: Enable Gradle's `--configuration-cache` flag via user settings.

**Changes**:
- Document and promote `java.import.gradle.arguments` setting with `--configuration-cache`
- **`build-server-for-gradle`**: Ensure configuration cache compatibility
- Consider enabling by default for projects with `gradle.properties` containing `org.gradle.configuration-cache=true`

**Estimated Impact**: After first import, subsequent opens could be **50-80% faster** for projects that support configuration cache.

---

## Priority Matrix

| # | Proposal | Impact | Effort | Risk | Priority |
|---|---------|--------|--------|------|----------|
| 3 | Cache `workspaceBuildTargets()` | High | Low | Low | **P0** |
| 2 | Batch BSP calls | High | Medium | Low | **P0** |
| 5 | Batch DigestStore serialization | Medium | Low | Low | **P0** |
| 1 | Progressive project loading | Very High | Medium | Medium | **✅ Done** |
| 4 | Parallel classpath updates | Medium | Medium | Medium | **P1** |
| 7 | Build server pre-warming | Medium | Low | Low | **P1** |
| 8 | Gradle configuration cache | High | Low | Low | **P1** |
| 6 | Lazy tree view population | Medium | Medium | Low | **P2** |
| 1B | Streaming BSP project import | Very High | High | High | **P2** |

---

## Quick Wins Checklist

These can be implemented immediately with minimal risk:

- [x] **Progressive project loading in tree view** — projects appear in ~2s instead of waiting for full import (Proposal 1 — implemented)
- [ ] **Cache `workspaceBuildTargets()` in `importToWorkspace()`** — pass cached result to `importProjects()`, `updateClasspath()`, and `updateProjectDependencies()`
- [ ] **Batch BSP `buildTargetOutputPaths/Sources/Resources/DependencyModules`** — collect all target IDs, make 4 calls instead of 4N
- [ ] **Batch `DigestStore.updateDigest()`** — collect all paths, serialize once at end
- [ ] **Pre-warm Gradle daemon** — start connection in `applies()` asynchronously
- [ ] **Document `--configuration-cache`** — add to README/settings description

---

## Files to Modify

| File | Proposals |
|------|-----------|
| `vscode-gradle/.../GradleBuildServerProjectImporter.java` | #2, #3, #4, #5, #7 |
| `vscode-gradle/.../GradleBuildServerBuildSupport.java` | #2, #3 |
| `vscode-gradle/.../Utils.java` | #3 |
| `eclipse.jdt.ls/.../managers/ProjectsManager.java` | ✅ #1 (progressive notifications) |
| `eclipse.jdt.ls/.../handlers/JDTLanguageServer.java` | ✅ #1 (INDEX_INDEPENDENT_COMMANDS) |
| `eclipse.jdt.ls/.../managers/DigestStore.java` | #5 |
| `vscode-java/src/apiManager.ts` | ✅ #1 (serverRunning API) |
| `vscode-java/src/extension.api.ts` | ✅ #1 (API v0.14) |
| `vscode-java/src/standardLanguageClient.ts` | ✅ #1 (resolveServerRunningPromise) |
| `vscode-java-dependency/src/commands.ts` | ✅ #1 (ADD_PROJECTS command) |
| `vscode-java-dependency/src/languageServerApi/languageServerApiManager.ts` | ✅ #1 (client-side progressive rendering) |
| `vscode-java-dependency/src/views/dependencyDataProvider.ts` | ✅ #1 (addProgressiveProjects, fast path), #6 |
| `vscode-java-dependency/.../ProjectCommand.java` | #6B |
| `vscode-gradle/extension/build-server-for-gradle/` | #1B, #8 |

---

## Verification Plan

1. **Before/After Timing**: Open spring-boot project, measure time from JDTLS `initialize` to first project visible in tree view
2. **BSP Call Count**: Add logging to `Utils.getBuildTargetsByProjectUri()` / `getBuildTargetsMappedByProjectPath()` to count invocations before and after caching
3. **Regression**: Ensure all existing JDTLS tests pass (`./mvnw clean verify`)
4. **Stress Test**: Verify with other large Gradle projects (e.g., Android AOSP modules, Micronaut framework)
5. **DigestStore**: Verify digest state is correctly flushed on shutdown

---

## Appendix: Estimated Time Breakdown for 702s

| Phase | Est. Time | % | Root Cause |
|-------|-----------|---|-----------|
| `buildInitialize().join()` (Gradle eval + dependency resolution) | ~580-630s | ~85% | Gradle evaluates 400+ build files, resolves deps |
| Per-target BSP calls (`updateClasspath` × 400 projects) | ~40-80s | ~8% | 3200+ sequential blocking RPCs |
| Redundant `workspaceBuildTargets()` (800+ calls) | ~10-20s | ~2% | Full target list fetched/filtered per project |
| DigestStore serialization thrashing | ~5-10s | ~1% | 1600 full HashMap serializations |
| Project creation + nature configuration | ~5-10s | ~1% | IProject/Eclipse workspace operations |
| Other (configureFilters, registerWatchers, etc.) | ~2-5s | <1% | — |
