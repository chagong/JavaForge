---
name: vscode-probe
description: Discover how VS Code (or a VS Code extension) implements a feature — its functionality and UX — by spawning VS Code, automating it with playwright-cli, and producing structured functional + UX requirements.
allowed-tools: Bash(playwright-cli:*) Bash(node:*) Bash(npm:*) Bash(npx:*)
---

# Discovering VS Code Feature Behaviour

Use this skill when you need to understand how VS Code or a VS Code extension implements a specific feature. You will spawn a live VS Code instance, interact with the feature systematically, capture screenshots and accessibility snapshots, and produce a structured requirements document.

**Input**: a feature description (e.g., "allow commands in the session", "Copilot inline chat")  
**Output**: functional requirements + UX requirements

## How it works

1. `scripts/launch-vscode.js` starts VS Code with `--remote-debugging-port=9222` to expose its Chromium DevTools Protocol endpoint
2. `playwright-cli attach --cdp` connects to the running VS Code instance
3. You navigate to the feature and interact with it, taking screenshots and accessibility snapshots at each step
4. **As you discover each requirement, you write it down immediately** into `features/${FEATURE_SLUG}.md` — do not wait until the end
5. By the time probing is finished, the requirements document is complete

## Prerequisites (run once)

```bash
# Install playwright-cli globally
npm install -g @playwright/cli@latest

# Install skill dependencies (downloads @vscode/test-electron as fallback)
cd .github/skills/vscode-probe && npm install
```

---

## Step 0 — Create a run folder

Before doing anything else, create a timestamped folder under `runs/` at the repo root. All screenshots and accessibility snapshots for this run go there. The final requirements document goes under `features/`.

```bash
# Generate a filesystem-safe timestamp: YYYYMMDD-HHmmss
RUN_TS=$(date +"%Y%m%d-%H%M%S")           # Linux/macOS
# PowerShell: $RUN_TS = Get-Date -Format "yyyyMMdd-HHmmss"

# Derive a slug from the feature being probed (lowercase, hyphens)
FEATURE_SLUG="<feature-slug>"             # e.g. "allow-commands"

RUN_DIR="runs/${RUN_TS}-${FEATURE_SLUG}"
mkdir -p "$RUN_DIR"
echo "Run folder: $RUN_DIR"
```

Also **initialise the output file immediately** so you can append to it throughout the session:

```bash
FEATURE_FILE="features/${FEATURE_SLUG}.md"
cat > "$FEATURE_FILE" << EOF
# Feature: ${FEATURE_SLUG}

### Functional Requirements

| ID | Requirement |
|----|-------------|

### UX Requirements

| ID | Requirement |
|----|-------------|

### Key Screenshots

| File | State captured |
|------|----------------|
EOF
echo "Requirements file: $FEATURE_FILE"
```

> **Rule**: every `--filename` argument in the steps below must be prefixed with `$RUN_DIR/`.  
> **Rule**: the final requirements document is saved as `features/${FEATURE_SLUG}.md`.  
> **Rule**: key screenshots are copied to `features/screenshots/${FEATURE_SLUG}/` in Step 5 and linked from the Key Screenshots table using those paths.

---

## Step 1 — Launch VS Code

```bash
node .github/skills/vscode-probe/scripts/launch-vscode.js            # VS Code Insiders (default)
node .github/skills/vscode-probe/scripts/launch-vscode.js stable     # stable VS Code
```

This script finds your system VS Code Insiders first, falling back to stable if not installed. If neither is found, it downloads the requested version via `@vscode/test-electron`. VS Code launches with CDP on port 9222 and the script prints ready instructions.

Override the port or path:
```bash
CDP_PORT=9223 node .github/skills/vscode-probe/scripts/launch-vscode.js
VSCODE_PATH="C:\path\to\Code - Insiders.exe" node .github/skills/vscode-probe/scripts/launch-vscode.js
```

> **Important — use an isolated profile.** If a VS Code instance is already running, a plain launch with `--remote-debugging-port` opens a new window *inside the existing process*, which ignores the debug flag — so CDP never comes up. Always launch a **separate process with its own `--user-data-dir`** (e.g. `scratch/cdp-user-data`). This also keeps your real editor untouched and makes teardown safe (you can kill only the processes bound to that profile). Example:
>
> ```powershell
> & 'C:\Users\<you>\AppData\Local\Programs\Microsoft VS Code\Code.exe' `
>   --remote-debugging-port=9222 `
>   --user-data-dir='<repo>\scratch\cdp-user-data' `
>   --no-first-run '<repo>\<folder-to-open>'
> ```
>
> On VS Code **Insiders**, a pending auto-update can hold a mutex lock (`Error: mutex already exists`) and block the isolated launch. If that happens, fall back to **stable** VS Code.

Keep VS Code running. Do not close it between probing steps.

---

## Step 2 — Attach playwright-cli

```bash
playwright-cli attach --cdp=http://localhost:9222
playwright-cli tab-list
```

VS Code exposes multiple CDP targets (workbench, extension host worker, shared process, webviews). `tab-list` lists them all. The main workbench is the target whose title contains "Visual Studio Code". Switch to it if not already selected:

```bash
playwright-cli tab-select <index>   # index from tab-list output
playwright-cli snapshot             # capture initial accessibility tree
```

> **Webview panels** (Copilot Chat, extensions) render as separate CDP targets with titles like "Webview". Switch to the correct target before interacting with panel content.

---

## Step 3 — Navigate to the feature

Use VS Code keyboard shortcuts via playwright-cli:

```bash
# Command Palette — discover any feature by name
playwright-cli press "Control+Shift+P"
playwright-cli snapshot
playwright-cli type "feature name here"
playwright-cli screenshot --filename=$RUN_DIR/01-command-palette.png

# Open Copilot Chat panel
playwright-cli press "Control+Alt+I"

# Open Settings UI
playwright-cli press "Control+Comma"

# Open Extensions view
playwright-cli press "Control+Shift+X"

# Open integrated terminal
playwright-cli press "Control+Backtick"

# Copilot Inline Chat (requires editor focus)
playwright-cli press "Control+I"
```

**Always take a screenshot immediately after opening the feature:**
```bash
playwright-cli screenshot --filename=$RUN_DIR/01-feature-open.png
playwright-cli snapshot --filename=$RUN_DIR/01-feature-open.yml
```

---

## Step 4 — Probe the feature systematically

Follow this loop for every meaningful UI state. **After each observation, immediately append any new requirement to `$FEATURE_FILE` — do not batch them for later.**

```bash
# Before interacting — capture current state
playwright-cli screenshot --filename=$RUN_DIR/<NN>-<state>.png
playwright-cli snapshot --filename=$RUN_DIR/<NN>-<state>.yml

# Interact
playwright-cli click <ref>
playwright-cli type "test input"
playwright-cli press Enter
playwright-cli hover <ref>

# After interacting — capture result
playwright-cli screenshot --filename=$RUN_DIR/<NN>-after.png
playwright-cli snapshot --filename=$RUN_DIR/<NN>-after.yml

# ✏️  Write down what you just observed — RIGHT NOW, not later
# Append a row to the FR or UX table in $FEATURE_FILE, e.g.:
# | FR-1 | The send button is disabled until the input field is non-empty |
# | UX-3 | A spinner replaces the send icon while the request is in-flight |
# Also append a row to the Key Screenshots table:
# | `$RUN_DIR/03-send-button-disabled.png` | Send button in disabled state |
```

> **Rule**: treat every screenshot + snapshot as a prompt to write. If you took a screenshot, you observed something — record it before moving on.

### States to cover for every feature

| State | What to capture |
|---|---|
| **Entry point** | How the user opens/triggers the feature (menu, shortcut, button, command) |
| **Initial / idle** | What the UI looks like before any interaction |
| **Active / loading** | Is there a spinner, progress bar, or streaming indicator? |
| **Success** | What does the UI show on a successful operation? |
| **Error** | What happens on invalid input, network failure, or refusal? |
| **Empty** | What does the UI show with no data / no results? |
| **Hover / focus** | Does any element change appearance on hover or keyboard focus? |
| **Keyboard-only** | Can the feature be fully operated without a mouse? |
| **Disabled / restricted** | Are any controls conditionally disabled? When and why? |

### Examining element details

```bash
# Get aria-label, data-* attributes, or computed text not visible in snapshot
playwright-cli eval "el => el.getAttribute('aria-label')" <ref>
playwright-cli eval "el => el.dataset.vscodeContext" <ref>
playwright-cli eval "el => el.className" <ref>

# Inspect VS Code's when-clause context (for command palette entries)
playwright-cli eval "document.querySelector('.action-label[aria-label=\"...\"]')?.closest('[data-keybinding-context]')?.dataset.keybindingContext"
```

### Capturing visual appearance of a specific element

When checking the visual effect of a single element (hover state, focus ring, disabled style, animation, etc.), screenshot just that element instead of the full window. This produces a tighter, more readable image:

```bash
# Screenshot a single element by its ref
playwright-cli screenshot --filename=$RUN_DIR/<NN>-<element>-state.png <ref>

# Examples
playwright-cli screenshot --filename=$RUN_DIR/03-send-button-hover.png e12
playwright-cli screenshot --filename=$RUN_DIR/05-input-focused.png e7
playwright-cli screenshot --filename=$RUN_DIR/07-toggle-on.png e4
```

Use this whenever you are documenting **Hover / focus**, **Disabled / restricted**, or any per-element visual state in the UX requirements.

---

## Step 5 — Copy key screenshots and finalise requirements

By this point `features/${FEATURE_SLUG}.md` should already be populated from the live-writing in Step 4.

### 5a — Copy key screenshots to the feature folder

Pick the most illustrative screenshots (one per distinct UI state) and copy them next to the feature doc. This keeps the screenshots in git alongside the requirements doc, independent of the timestamped run folder.

```bash
# PowerShell
$IMG_DIR = "features\screenshots\${FEATURE_SLUG}"
New-Item -ItemType Directory -Force -Path $IMG_DIR | Out-Null

# Copy each key screenshot — rename to a descriptive slug
Copy-Item "$RUN_DIR\03-input-idle.png"        "$IMG_DIR\input-idle.png"
Copy-Item "$RUN_DIR\07-autocomplete-open.png" "$IMG_DIR\autocomplete-open.png"
# … repeat for every screenshot you want to keep
```

Update the Key Screenshots table in the feature doc to reference the new paths:

```markdown
| File | State captured |
|------|----------------|
| `features/screenshots/<slug>/input-idle.png` | Chat input in idle state |
| `features/screenshots/<slug>/autocomplete-open.png` | Slash-command autocomplete open |
```

> **Rule**: only copy screenshots that are genuinely useful for understanding the feature. 3–8 images per feature is typical. Raw run screenshots (dozens of incremental captures) stay in `$RUN_DIR/` and are gitignored.

### 5b — Final review pass

1. Fill any gaps — states you observed but didn't write down yet
2. Assign sequential IDs (`FR-1`, `FR-2` … `UX-1`, `UX-2` …) if not already done
3. Verify every row in the Key Screenshots table points to a file that exists under `features/screenshots/`
4. Remove placeholder rows left from the initial template

The file is already in place — no bulk-paste needed.

---

## Feature: `<feature name>`

### Functional Requirements

| ID | Requirement |
|----|-------------|
| FR-1 | Describe the observable behaviour triggered by the feature |
| FR-2 | Entry points: how is the feature accessed? (command ID, shortcut, menu path) |
| FR-3 | State machine: what transitions occur and under what conditions? |
| FR-4 | Data: what is the input, output, and any persistence? |
| FR-5 | Permissions / guards: when is the feature available vs. disabled? |
| FR-6 | Error conditions: what triggers errors and how are they surfaced? |

### UX Requirements

| ID | Requirement |
|----|-------------|
| UX-1 | Layout: describe the visual structure (panel, inline, overlay, status bar) |
| UX-2 | Controls: list every interactive element and its type (button, input, toggle, dropdown) |
| UX-3 | Feedback: loading indicators, streaming output, toasts, status messages |
| UX-4 | Keyboard: shortcuts, tab order, focus trapping, escape behaviour |
| UX-5 | States: describe the visual appearance for empty, loading, success, error states |
| UX-6 | Motion: any animations, transitions, or scroll behaviour |
| UX-7 | Accessibility: aria labels, roles, screen-reader announcements observed in snapshots |

### Key Screenshots

| File | State captured |
|---------|----------------|
| `features/screenshots/<slug>/01-*.png` | ... |
| `features/screenshots/<slug>/02-*.png` | ... |

---

## VS Code UI quick reference

### Keyboard shortcuts

| Action | Shortcut |
|--------|----------|
| Command Palette | `Control+Shift+P` |
| Quick Open file | `Control+P` |
| Settings UI | `Control+Comma` |
| Extensions view | `Control+Shift+X` |
| Source Control | `Control+Shift+G` |
| Integrated Terminal | `Control+Backtick` |
| Copilot Chat | `Control+Alt+I` |
| Copilot Inline Chat | `Control+I` |
| Toggle Sidebar | `Control+B` |
| Close active editor | `Control+W` |
| Split editor | `Control+\\` |

### Accessibility locators (prefer over ref IDs)

VS Code's accessibility tree uses `aria-label` and ARIA roles extensively. Prefer these stable locators:

```bash
# Activity Bar items
playwright-cli click "getByRole('tab', { name: 'Explorer' })"
playwright-cli click "getByRole('tab', { name: 'Copilot' })"
playwright-cli click "getByRole('tab', { name: 'Extensions' })"

# Command palette
playwright-cli click "getByRole('combobox', { name: 'input' })"

# Chat input (inside Copilot Chat webview)
playwright-cli click "getByRole('textbox', { name: 'Ask Copilot' })"
playwright-cli fill "getByRole('textbox', { name: 'Ask Copilot' })" "hello"

# Buttons
playwright-cli click "getByRole('button', { name: 'Send' })"
playwright-cli click "getByRole('button', { name: 'Allow' })"
playwright-cli click "getByRole('button', { name: 'Accept' })"

# Checkboxes / toggles
playwright-cli check "getByRole('checkbox', { name: 'Enable ...' })"

# Menus
playwright-cli click "getByRole('menuitem', { name: 'Settings' })"
```

### Navigating Copilot Chat webview

Copilot Chat renders inside a webview iframe — it appears as a separate CDP target:

```bash
playwright-cli tab-list          # find the "Webview" target for Copilot Chat
playwright-cli tab-select <N>    # switch to that target
playwright-cli snapshot          # see the webview's accessibility tree
```

Within the webview, elements use standard HTML roles. Chat messages are typically `role="article"` or inside a scrollable container.

---

## Example: Probing "allow commands in the session"

```bash
# 0. Create run folder
RUN_TS=$(date +"%Y%m%d-%H%M%S")
FEATURE_SLUG="allow-commands"
RUN_DIR="runs/${RUN_TS}-${FEATURE_SLUG}"
mkdir -p "$RUN_DIR"

# 1. Start VS Code and attach
node .github/skills/vscode-probe/scripts/launch-vscode.js
playwright-cli attach --cdp=http://localhost:9222

# 2. Baseline screenshot
playwright-cli screenshot --filename=$RUN_DIR/00-initial.png

# 3. Open Copilot Chat
playwright-cli press "Control+Alt+I"
playwright-cli screenshot --filename=$RUN_DIR/01-chat-open.png
playwright-cli snapshot --filename=$RUN_DIR/01-chat-open.yml

# 4. Check the current mode / permissions area
playwright-cli tab-list                      # find Copilot Chat webview target
playwright-cli tab-select <N>
playwright-cli snapshot --filename=$RUN_DIR/02-chat-webview.yml

# 5. Find and inspect the "allow commands" control
#    Read the snapshot to find a ref for the toggle/button
playwright-cli screenshot --filename=$RUN_DIR/03-commands-state-off.png

playwright-cli click <ref-for-allow-toggle>
playwright-cli screenshot --filename=$RUN_DIR/04-commands-state-on.png
playwright-cli snapshot --filename=$RUN_DIR/04-commands-state-on.yml

# 6. Test what happens when a command runs
playwright-cli fill "getByRole('textbox', { name: 'Ask Copilot' })" "run: echo hello"
playwright-cli press Enter
playwright-cli screenshot --filename=$RUN_DIR/05-command-running.png
playwright-cli screenshot --filename=$RUN_DIR/06-command-result.png
playwright-cli snapshot --filename=$RUN_DIR/06-command-result.yml

# 7. Close (detaches CDP; see Troubleshooting to fully kill the isolated VS Code)
playwright-cli close

# 8. Save final requirements to features/
# (analyze screenshots/snapshots above, then write the document)
cat > features/${FEATURE_SLUG}.md << 'EOF'
# Feature: Allow Commands in the Session
...
EOF
```

After capturing these, analyze each screenshot and snapshot in `$RUN_DIR/` in sequence to fill out the FR + UX tables and write `features/${FEATURE_SLUG}.md`.

---

## Troubleshooting

### `playwright-cli attach` fails / no targets listed

VS Code may not have exposed the CDP port yet. Wait a few seconds and retry. If VS Code was already running before launch, restart it via the script.

### Wrong target selected — snapshot shows extension host or worker

Use `playwright-cli tab-list` and `playwright-cli tab-select` to switch targets. The main workbench has a title like `"Visual Studio Code"`.

### Copilot Chat content not visible in snapshot

The chat panel is a webview — it appears as a separate CDP target. Run `playwright-cli tab-list` to find the target whose title includes `"Webview"` or the extension name, then `tab-select` to switch.

### VS Code opens but CDP is not ready

Some VS Code versions require `--remote-debugging-address=127.0.0.1` in addition to `--remote-debugging-port`. Set `VSCODE_PATH` to a known executable and re-run the launch script.

### `playwright-cli close` left VS Code running

`playwright-cli close` only **detaches the CDP session** — it does not terminate a VS Code process it merely attached to. To fully tear down, kill the processes bound to your isolated profile (this leaves your real editor alone). On Windows/PowerShell:

```powershell
Get-CimInstance Win32_Process -Filter "Name='Code.exe'" |
  Where-Object { $_.CommandLine -like '*cdp-user-data*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

On Linux/macOS, match the same `--user-data-dir` path with `pkill -f`:

```bash
pkill -f 'cdp-user-data'
```

Leftover profile folders under `scratch/cdp-user-data*` are gitignored and can be deleted between runs.

### Reading long Output/log channels — only ~14 lines visible

The Monaco editor **virtualizes** content: the DOM only contains the lines currently in the viewport (~14), not the full log. To read a long channel, either scroll programmatically and concatenate the `.view-line` text across steps, or read the on-disk log file directly. CDP is best for *interactive* channel selection and reading visible text, not bulk log extraction.
