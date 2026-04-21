# MavenProjectImporter — Performance Analysis

## Overall Import Pipeline

The import flows through these sequential phases:

```
applies() → importToWorkspace() → updateProjects()
   │              │                      │
   ├─ BasicFileDetector.scan()           ├─ configurationManager.importProjects()   ├─ MavenBuildSupport.update() [async]
   ├─ LocalProjectScanner.run()          └─ DigestStore.updateDigest() × N          └─ configurationManager.updateProjectConfiguration()
```

---

## Bottleneck 1: DigestStore serializes to disk on EVERY single file change

**File**: `eclipse.jdt.ls/org.eclipse.jdt.ls.core/src/org/eclipse/jdt/ls/core/internal/managers/DigestStore.java` (L68-80)

`updateDigest()` calls `serializeFileDigests()` which writes the **entire** `HashMap` via `ObjectOutputStream` on every call.

In `MavenProjectImporter.importToWorkspace()` (L175-195), `digestStore.updateDigest(pom.toPath())` is called **once per project** in the classification loop. For a workspace with 100 Maven modules, this means **100 full serializations** of the digest map to disk during initial import.

**Impact**: O(N²) disk I/O — each serialization writes the growing map. For large workspaces this is significant.

**Fix**: Batch digest updates — add an `updateDigests(Collection<Path>)` method or a `flush()` pattern that defers serialization until all digests are computed.

---

## Bottleneck 2: Double POM scanning — BasicFileDetector + LocalProjectScanner

The `applies()` phase uses `BasicFileDetector` to walk the file tree and find all `pom.xml` files (L97-108). Then `getMavenProjectInfo()` invokes m2e's `LocalProjectScanner` which performs **its own recursive scan** of the same directories to build `MavenProjectInfo` objects (L336-340).

Two full file-system walks of the same tree. `BasicFileDetector` walks with `maxDepth=5`, follows symlinks, and checks exclusions. `LocalProjectScanner` then walks again, parsing each `pom.xml` into a Maven Model.

**Impact**: Doubles the I/O cost of the discovery phase, especially significant on network drives or large monorepos.

**Fix**: Could pass the discovered directory paths directly to m2e's model resolution without a second scan, or merge the two into one pass.

---

## Bottleneck 3: Sequential project-by-project update in `updateProjects()`

**File**: `eclipse.jdt.ls/org.eclipse.jdt.ls.core/src/org/eclipse/jdt/ls/core/internal/managers/MavenProjectImporter.java` (L309-325)

The async `WorkspaceJob` iterates projects sequentially:

```java
for (IProject project : projects) {
    mavenBuildSupport.update(project, false, monitor);
}
```

Each `update()` call triggers `configurationManager.updateProjectConfiguration()` which resolves dependencies from remote/local repositories, runs lifecycle mappings, and updates the `.classpath`. These are individual m2e calls — **no batching or parallelism**.

**Impact**: For N existing projects that need update, this is N sequential Maven dependency resolutions. Each can involve network I/O to download/check artifacts.

**Fix**: The code already has `shouldCollectProjects=false` here (disabling recursive module collection), but it doesn't use the batched `MavenUpdateRequest(Collection<IProject>, ...)` constructor. All projects could be submitted in a single `MavenUpdateRequest` to let m2e optimize its internal resolution.

---

## Bottleneck 4: Windows-specific double refresh

**File**: `eclipse.jdt.ls/org.eclipse.jdt.ls.core/src/org/eclipse/jdt/ls/core/internal/managers/MavenProjectImporter.java` (L298-304)

```java
if (Platform.OS_WIN32.equals(Platform.getOS())) {
    project.refreshLocal(IResource.DEPTH_ONE, monitor);
    ((Workspace) ResourcesPlugin.getWorkspace()).getRefreshManager().refresh(project);
} else {
    project.refreshLocal(IResource.DEPTH_INFINITE, monitor);
}
```

On Windows, each project is refreshed twice — once with `DEPTH_ONE`, then again via the `RefreshManager`. This is done for every project in the update set, and the refresh operations touch the filesystem and update Eclipse's resource model.

**Impact**: Noticeable on Windows with many projects, especially on NTFS with large directory trees.

---

## Bottleneck 5: `includeNested(false)` forces a separate LocalProjectScanner pass

In `applies()`, `BasicFileDetector` is set to `includeNested(false)`, meaning it stops descending into subdirectories once a `pom.xml` is found. This means only **root-level** `pom.xml` files are discovered. The subsequent `LocalProjectScanner.run()` then needs to discover all nested modules by parsing the parent POM and recursively resolving `<modules>`.

This is architecturally correct (avoids importing submodules as standalone projects) but means the module tree discovery is entirely deferred to m2e's `LocalProjectScanner`, which parses every `pom.xml` to build the model graph — a potentially expensive operation for deep multi-module hierarchies.

---

## Bottleneck 6: No parallelism in the import path

The entire `importToWorkspace()` method is single-threaded:

1. **Scan** directories (single thread)
2. **Classify** each project as new/existing (single thread, O(N) digest updates)
3. **Import** via m2e (single thread, or batched-sequential for >50 projects)
4. **Update** existing projects (single thread in WorkspaceJob)

The workspace's `maxConcurrentBuilds` setting enables parallel m2e **builds**, but the **import** path doesn't use it. Compare this with `GradleBuildServerProjectImporter` which can parallelize via BSP over multiple projects.

---

## Bottleneck 7: `collectProjects()` in MavenBuildSupport creates facade per project

**File**: `eclipse.jdt.ls/org.eclipse.jdt.ls.core/src/org/eclipse/jdt/ls/core/internal/managers/MavenBuildSupport.java` (L90-106)

When `shouldCollectProjects=true` (the default for file-change triggers), `registry.create(project, monitor)` is called for each project and its modules recursively. The `create()` call forces m2e to build a `MavenProjectFacade`, which involves parsing the POM, resolving parent POMs, and potentially hitting remote repositories.

During import this is mitigated by `setShouldCollectProjects(false)`, but during subsequent POM edits (file change events), this recursive facade creation runs for every save.

---

## Summary Table

| # | Bottleneck | Phase | Severity | Where |
|---|-----------|-------|----------|-------|
| 1 | DigestStore serializes on every update | classify | **High** for large workspaces | `DigestStore.updateDigest()` |
| 2 | Double filesystem scan (BasicFileDetector + LocalProjectScanner) | discover | **Medium** | `applies()` + `getMavenProjects()` |
| 3 | Sequential per-project update (no batching to m2e) | update | **High** | `updateProjects()` WorkspaceJob |
| 4 | Double refresh on Windows | update | **Medium** (Windows-only) | `updateProjects()` |
| 5 | Nested module discovery deferred to m2e POM parsing | discover | **Low-Medium** | architectural |
| 6 | Fully single-threaded import pipeline | overall | **Medium** | `importToWorkspace()` |
| 7 | Recursive facade creation on file changes | runtime | **Medium** | `MavenBuildSupport.collectProjects()` |

## Recommended Priority

The most impactful quick wins would be:

1. **Batching DigestStore serialization** (#1) — straightforward code change, large impact on workspaces with many modules
2. **Batching `updateProjectConfiguration` calls** (#3) — submit all projects in a single `MavenUpdateRequest` instead of one-by-one
3. **Eliminating the double scan** (#2) — pass `BasicFileDetector` results directly to m2e model resolution
