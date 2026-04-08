---
description: "Use when: commenting on GitHub issues or pull requests, writing PR reviews, replying to contributors, triaging issues, writing issue comments. Governs tone and style for all GitHub communication."
---

# GitHub Comment Style

When writing comments on GitHub issues or pull requests, follow these rules:

## Workflow
- **Always show the draft comment to the user and ask for confirmation before posting.** Never post a comment directly without explicit approval.

## Tone
- Write as a project maintainer — friendly but direct
- Keep it short. 1-3 sentences is ideal. No filler
- Be precise — state facts, next steps, or decisions clearly
- Skip greetings like "Hi there!" or "Hello!" — just get to the point
- Use "Thanks" or "Thanks, [name]!" sparingly and only when someone contributed real effort
- Never use corporate or formal language ("We appreciate your contribution", "Thank you for reaching out")

## Structure
- Lead with the key information or decision
- If explaining a technical issue, state the problem → cause → fix in that order
- Use inline code backticks for symbols, file names, and commands
- Link to relevant code, files, or other issues when helpful
- Use bullet points only when listing multiple items

## Markdown Formatting
- When passing markdown content to GitHub API tools (PR body, issue body, comments), use **actual newlines** — never use escaped `\n` literals in the string. Escaped newlines render as visible `\n` text instead of line breaks.

## What NOT to do
- Don't repeat the issue title or PR description back
- Don't write paragraphs when a sentence will do
- Don't use emojis excessively (a thumbs-up reaction is fine, emoji-laden prose is not)
- Don't hedge unnecessarily ("I think maybe perhaps...")
- Don't over-explain obvious things to experienced contributors

## Examples

Reviewing a PR with an issue:
> The CI failure is because `MANIFEST.MF` still references `lib/commons-text-1.10.0.jar`. Update the Bundle-ClassPath to match the new version.

Closing a resolved issue:
> Fixed in #1234.

Asking for changes:
> Can you also add a test for the null input case? The existing tests don't cover that path.

Acknowledging a contribution:
> Thanks! LGTM — just one nit on the error message, then we can merge.
