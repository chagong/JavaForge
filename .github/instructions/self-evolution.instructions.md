---
description: "Use when: the user corrects a mistake, points out a gap in agent behavior, or you discover a workaround that should be permanent. Governs updating skills, instructions, and prompts to prevent recurrence of issues."
---

# Self-Evolution

When a mistake, inefficiency, or gap is identified during a task, update the relevant workspace configuration files so the same issue doesn't recur in future sessions.

## When to Trigger

- The user explicitly corrects your output or approach
- You discover a tool quirk or API behavior that caused a wrong result (e.g., escaped newlines in API calls)
- A workaround was needed that should be codified as a rule
- A skill's procedure is missing a step or has an incorrect command
- An instruction file doesn't cover a scenario it should

## Procedure

### 1. Identify the Root Cause

Determine **why** the mistake happened:
- Missing rule in an instruction file?
- Incomplete procedure in a skill?
- Tool behavior not documented?
- Wrong default assumption?

### 2. Find the Right Config File

Scan the workspace `.github/` directory to locate the relevant file:

1. **List** `.github/instructions/`, `.github/skills/`, and `.github/prompts/` to see all current config files.
2. **Match by domain**: Read the frontmatter `description` of candidate files to find the one that governs the area where the mistake occurred.
3. **Workspace-wide rules** live in `.github/copilot-instructions.md` — only update this for cross-cutting concerns (repo mapping, build commands, CI requirements).
4. If no existing file covers the area, propose creating a new instruction or skill in the appropriate directory.

### 3. Apply the Update

- **Be surgical**: Add or modify only the specific rule. Don't restructure or refactor the file.
- **Be concrete**: State the exact behavior, not vague guidance. Include code examples or tool invocation patterns when relevant.
- **Be brief**: One bullet point or short paragraph per lesson. Don't add lengthy explanations.
- **Place correctly**: Add new rules to the most relevant existing section. Create a new section only if nothing fits.

### 4. Confirm with the User

After making the update, briefly state what was changed and why, so the user can verify.

## Rules

- Only update config files when a real issue was encountered — don't speculatively add rules.
- If the fix belongs in multiple files, update all of them.
- Don't duplicate rules across files. If a rule applies to one domain (e.g., GitHub comments), put it in that domain's instruction file, not in `copilot-instructions.md`.
