---
name: send-teams-notification
description: Send personal notifications to individuals via Teams personal chat using Azure Logic App. Use when (1) sending any message to a person's Teams chat, (2) delivering reports, summaries, or alerts to specific recipients, (3) notifying someone about updates, results, or action items. Triggers on requests like "send teams notification", "notify user", "send message to", "teams message".
---

# Send Teams Notification Skill

Send messages to Microsoft Teams personal chat via an Azure Logic App HTTP trigger.

## Overview

This skill posts a JSON payload to a configured Logic App endpoint, which delivers a message directly to a specified recipient's Teams personal chat. It can be used for any type of notification — reports, alerts, status updates, action items, or general messages.

## Usage

### Required Environment Variable

The notification URL must be set via environment variable:
- `PERSONAL_NOTIFICATION_URL`: The Azure Logic App HTTP trigger URL for personal notifications

### Input Format

The payload should be a JSON object with the following example:

```json
{
  "title": "Build completed for vscode-java v1.38.0",
  "message": "## Build Result\n\nThe release build for **vscode-java v1.38.0** completed successfully.\n\n- All 342 tests passed\n- VSIX artifact uploaded\n- No lint warnings",
  "recipient": "johndoe@microsoft.com"
}
```

With optional `workflowRunUrl`:

```json
{
  "title": "Daily Issue Triage Report - April 13, 2026",
  "message": "## Triage Summary\n\n5 issues triaged today. 2 SLA violations, 2 compliant, 1 waiting on reporter.",
  "workflowRunUrl": "https://github.com/microsoft/vscode-java-pack/actions/runs/12345678/job/98765432",
  "recipient": "johndoe@microsoft.com"
}
```

For the full JSON schema, see [references/payload-schema.json](references/payload-schema.json).

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | string | Required | Title of the notification message |
| `message` | string | Required | Main content of the message (supports markdown) |
| `recipient` | string | Required | Email address of the recipient |
| `workflowRunUrl` | string | Optional | URL to a related workflow run, PR, or any relevant link |

## Workflow

1. Receive JSON payload from user or another skill/agent
2. **BLOCKING: Check that `PERSONAL_NOTIFICATION_URL` is set** — run `echo $env:PERSONAL_NOTIFICATION_URL` (PowerShell) or `echo $PERSONAL_NOTIFICATION_URL` (bash) and confirm it is non-empty. If it is empty or not set, **stop and ask the user** to provide the URL before proceeding. Do NOT attempt to send without a valid URL.
3. Validate that required fields are present (especially `recipient`)
4. POST the JSON payload to the Logic App endpoint
5. Report success or failure to the user

## Example Commands

- "Send a Teams notification to user@example.com about the build results"
- "Notify john@company.com that the release is ready for review"
- "Send a message to the assignee with the test failure details"
- "Send this triage summary as a Teams notification to user@example.com"

## Implementation

Use curl or equivalent HTTP client to POST the JSON:

```bash
curl -X POST "$PERSONAL_NOTIFICATION_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Notification Title",
    "message": "Message content with **markdown** support.",
    "recipient": "user@example.com"
  }'
```

## Response Handling

- **HTTP 2xx**: Teams notification sent successfully ✅
- **HTTP 4xx/5xx**: Failed to send notification ❌

Report the result to the user with the HTTP status code.

### CRITICAL: Never Retry Without Confirming Failure

**HTTP POST requests are not idempotent.** Each call sends a real message. If the terminal output appears truncated or incomplete, **do NOT re-send the request**. Instead:

1. Check the HTTP status code variable (e.g., `$sc` in PowerShell) in a **separate** follow-up command.
2. Only retry if you confirmed a non-2xx status code or a connection error.
3. If the status is ambiguous (no output at all), ask the user before retrying — they may have already received the message.

## Integration with Other Skills
