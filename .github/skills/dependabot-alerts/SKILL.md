---
name: dependabot-alerts
description: "Manage GitHub Dependabot alerts for any repo. Use when: listing dependabot alerts, viewing dependency vulnerability details, triaging dependabot alerts, dismissing or reopening dependabot alerts, checking vulnerable dependencies, fixing dependency vulnerabilities. Input: repo (owner/repo or URL) and optional filters."
argument-hint: 'owner/repo and command, e.g. "microsoft/vscode-gradle list-alerts --state open"'
---

# Dependabot Alerts

Interact with GitHub Dependabot vulnerability alerts via the REST API. Supports listing, inspecting, and updating alerts for dependency vulnerabilities.

## When to Use
- List open Dependabot alerts for a repository
- Get details of a specific alert (CVE, severity, vulnerable dependency, patched version)
- Dismiss or reopen alerts during triage
- Check which dependencies have known vulnerabilities
- Gather context for AI-assisted dependency upgrades

## Procedure

### Step 1: Identify the repo

Determine the `owner/repo` from the user's input. Accept any of:
- `owner/repo` string (e.g. `microsoft/vscode-gradle`)
- A GitHub URL (e.g. `https://github.com/microsoft/vscode-gradle`)
- A repo folder name from the workspace — map it using the table in `copilot-instructions.md`

### Step 2: Run the Python script

The script is at [scripts/dependabot_alerts.py](./scripts/dependabot_alerts.py). All commands follow this pattern:

```
python .github/skills/dependabot-alerts/scripts/dependabot_alerts.py <owner/repo> <command> [options]
```

#### Available Commands

**List alerts**
```bash
python .github/skills/dependabot-alerts/scripts/dependabot_alerts.py owner/repo list-alerts [--state open|dismissed|fixed|auto_dismissed] [--severity critical|high|medium|low] [--ecosystem npm|maven|pip|...] [--scope runtime|development] [--sort created|updated] [--direction asc|desc] [--per-page 30] [--before CURSOR] [--after CURSOR]
```

**Get a single alert**
```bash
python .github/skills/dependabot-alerts/scripts/dependabot_alerts.py owner/repo get-alert <alert_number>
```

**Update an alert** (dismiss or reopen)
```bash
python .github/skills/dependabot-alerts/scripts/dependabot_alerts.py owner/repo update-alert <alert_number> --state dismissed --reason "fix_started"|"inaccurate"|"no_bandwidth"|"not_used"|"tolerable_risk"
python .github/skills/dependabot-alerts/scripts/dependabot_alerts.py owner/repo update-alert <alert_number> --state open
```

### Step 3: Present results

- **For alert lists**: Summarize in a table with columns: number, state, severity, package, ecosystem, manifest, created date.
- **For single alert**: Show full details including the CVE/GHSA ID, description, vulnerable version range, patched version, and CVSS score.
- **For AI fixing**: After retrieving alert details, identify the manifest file (package.json, pom.xml, build.gradle, etc.), read it, and update the vulnerable dependency to the patched version.

### Step 4: AI-Assisted Fixing (when requested)

1. Run `get-alert <number>` to get the alert details, including the patched version.
2. Identify the manifest file from the alert's `dependency.manifest_path`.
3. Read the manifest file and update the dependency version.
4. After fixing, suggest running `update-alert` to dismiss with reason `fix_started`.

## Authentication

The script uses `GITHUB_TOKEN` env var, or falls back to `gh auth token` (GitHub CLI). Dependabot alerts API requires at minimum read access to Dependabot alerts on the repo.

## Notes
- Dependabot must be enabled on the target repo.
- Alert `state` can be: `open`, `dismissed`, `fixed`, `auto_dismissed`.
- Dismissed reasons: `fix_started`, `inaccurate`, `no_bandwidth`, `not_used`, `tolerable_risk`.
- The `--ecosystem` filter accepts: `npm`, `maven`, `pip`, `nuget`, `rubygems`, `composer`, `cargo`, `go`, `pub`, `actions`, etc.
- The `--scope` filter: `runtime` for production deps, `development` for dev deps.
