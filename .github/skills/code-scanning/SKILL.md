---
name: code-scanning
description: "Manage GitHub Code Scanning (CodeQL) alerts and analyses for any repo. Use when: listing code scanning alerts, viewing alert details, fetching CodeQL analysis results, triaging scanning alerts, getting alert instances, dismissing or reopening alerts, fixing code scanning issues. Input: repo (owner/repo or URL) and optional filters."
argument-hint: 'owner/repo and command, e.g. "microsoft/vscode-gradle list-alerts --state open"'
---

# Code Scanning

Interact with GitHub Code Scanning alerts and CodeQL analyses via the REST API. Supports listing, inspecting, and updating alerts, as well as listing analyses.

## When to Use
- List open code scanning alerts for a repository
- Get details of a specific alert (description, location, rule, severity)
- Fetch alert instances to see all locations where an issue appears
- List CodeQL analyses (completed scan runs) for a repo
- Get details of a specific analysis
- Dismiss or reopen alerts during triage
- Gather context for AI-assisted code fixes

## Procedure

### Step 1: Identify the repo

Determine the `owner/repo` from the user's input. Accept any of:
- `owner/repo` string (e.g. `microsoft/vscode-gradle`)
- A GitHub URL (e.g. `https://github.com/microsoft/vscode-gradle`)
- A repo folder name from the workspace — map it using the table in `copilot-instructions.md`

### Step 2: Run the Python script

The script is at [scripts/code_scanning.py](./scripts/code_scanning.py). All commands follow this pattern:

```
python .github/skills/code-scanning/scripts/code_scanning.py <owner/repo> <command> [options]
```

#### Available Commands

**List alerts**
```bash
python .github/skills/code-scanning/scripts/code_scanning.py owner/repo list-alerts [--state open|dismissed|fixed] [--severity critical|high|medium|low|warning|note|error] [--tool-name codeql] [--ref refs/heads/main] [--per-page 30] [--page 1]
```

**Get a single alert**
```bash
python .github/skills/code-scanning/scripts/code_scanning.py owner/repo get-alert <alert_number>
```

**List alert instances** (all locations where the alert fires)
```bash
python .github/skills/code-scanning/scripts/code_scanning.py owner/repo list-instances <alert_number> [--ref refs/heads/main] [--per-page 30] [--page 1]
```

**Update an alert** (dismiss or reopen)
```bash
python .github/skills/code-scanning/scripts/code_scanning.py owner/repo update-alert <alert_number> --state dismissed --reason "false positive"|"won't fix"|"used in tests"
python .github/skills/code-scanning/scripts/code_scanning.py owner/repo update-alert <alert_number> --state open
```

**List analyses** (CodeQL scan runs)
```bash
python .github/skills/code-scanning/scripts/code_scanning.py owner/repo list-analyses [--tool-name codeql] [--ref refs/heads/main] [--per-page 30] [--page 1]
```

**Get a single analysis**
```bash
python .github/skills/code-scanning/scripts/code_scanning.py owner/repo get-analysis <analysis_id>
```

### Step 3: Present results

- **For alert lists**: Summarize in a table with columns: number, rule, severity, state, file/line, created date.
- **For single alert**: Show full details including the rule description, affected code location, and any suggested fix from the rule help text.
- **For AI fixing**: After retrieving alert details/instances, read the affected source files and apply fixes informed by the rule description and `help` markdown.
- **For analyses**: Show analysis ID, tool, commit SHA, date, and alert counts (new/fixed/existing).

### Step 4: AI-Assisted Fixing (when requested)

1. Run `get-alert <number>` to get the alert details, rule description, and help text.
2. Run `list-instances <number>` to find all locations.
3. Read the affected source files.
4. Apply fixes following the guidance from the rule's `help` field.
5. After fixing, suggest running `update-alert` to dismiss with reason if appropriate.

## Authentication

The script uses `GITHUB_TOKEN` env var, or falls back to `gh auth token` (GitHub CLI). Code scanning APIs require at minimum read access to code scanning alerts on the repo.

## Notes
- Code scanning must be enabled on the target repo (via GitHub Actions CodeQL workflow or third-party SARIF uploads).
- The API returns up to 100 results per page. Use `--page` for pagination.
- Alert `state` can be: `open`, `dismissed`, `fixed`.
- Dismissed reasons: `false positive`, `won't fix`, `used in tests`.
- The `--ref` filter scopes results to a specific branch.
