---
name: send-teams-notification
description: Send personal notifications to individuals via Teams personal chat using Azure Logic App. Use when (1) sending any message to a person's Teams chat, (2) delivering reports, summaries, or alerts to specific recipients, (3) notifying someone about updates, results, or action items. Triggers on requests like "send teams notification", "notify user", "send message to", "teams message".
---

# Send Teams Notification Skill

Send messages to Microsoft Teams personal chat via an Azure Logic App HTTP trigger.

## Overview

This skill posts a JSON payload to a configured Logic App endpoint, which delivers a message directly to a specified recipient's Teams personal chat. It can be used for any type of notification — reports, alerts, status updates, action items, or general messages.

When the agent host exposes an externally installed `workiq` skill and its Teams tools, prefer that integration; it is not bundled with this repository and does not require `PERSONAL_NOTIFICATION_URL`. If unavailable, use the Logic App workflow below. Choose one transport, and never switch transports to retry an ambiguous send.

For WorkIQ chat messages, use `{"body":{"contentType":"html","content":"..."}}` without explicit `@odata.type` annotations. Teams can reject the schema-suggested `itemBody` type because its message endpoint expects `chatMessageBody`.

The instructions below apply only to the Logic App transport.

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
2. **BLOCKING: Resolve `PERSONAL_NOTIFICATION_URL`** using the [environment variable resolution instructions](../../instructions/env-variables.instructions.md). Check only whether the value is non-empty; never print the secret URL. If resolution fails, stop and ask the user to configure it before using the Logic App transport.
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
