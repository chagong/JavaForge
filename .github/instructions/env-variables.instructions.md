---
description: "Use when: a required environment variable is missing or empty. Governs the lookup order for resolving env vars needed by skills, scripts, or tools."
---

# Environment Variable Resolution

When a skill or task requires an environment variable that is not set in the current terminal session, resolve it using this fallback chain. **Stop at the first successful match.**

## Resolution Order

1. **System environment** — check presence without printing the value: `-not [string]::IsNullOrWhiteSpace($env:VAR_NAME)` (PowerShell) or `test -n "${VAR_NAME:-}"` (bash).
2. **Workspace `.env` file** — search for `VAR_NAME=value` in any `.env` file at the workspace root or repo roots:
   ```powershell
   $envMatches = Get-ChildItem -Path <workspace_root> -Filter ".env" -Depth 1 -Force | ForEach-Object { Select-String -Path $_.FullName -Pattern "^VAR_NAME=" }
   ```
   Parse the first non-empty value from the captured matches and set it in the current session before use. Do not print the matches.
3. **Agent memory** — check `/memories/` and `/memories/repo/` for previously stored values.
4. **Ask the user** — if none of the above yield a value, ask the user to provide it.

## Rules

- Always set the resolved value in the current terminal session (`$env:VAR_NAME = ...`) so subsequent commands in the same session can use it.
- Never print environment-variable values or matched `.env` lines; report only whether a value was found and its source.
- Never hard-code secret URLs or tokens in source files or memory. Only store them in `.env` (gitignored) or environment variables.
- If the `.env` file contains the value, do not ask the user — just use it silently.
