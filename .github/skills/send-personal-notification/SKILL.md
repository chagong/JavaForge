---
name: send-personal-notification
description: Send personal notifications to individuals via Teams personal chat using Azure Logic App. Use when (1) sending any message to a person's Teams chat, (2) delivering reports, summaries, or alerts to specific recipients, (3) notifying someone about updates, results, or action items. Triggers on requests like "send personal notification", "notify user", "send message to", "personal message".
---

# Send Personal Notification Skill

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
2. Validate that `PERSONAL_NOTIFICATION_URL` environment variable is set
3. Validate that required fields are present (especially `recipient`)
4. POST the JSON payload to the Logic App endpoint
5. Report success or failure to the user

## Example Commands

- "Send a personal notification to user@example.com about the build results"
- "Notify john@company.com that the release is ready for review"
- "Send a message to the assignee with the test failure details"
- "Send this triage summary as a personal notification to user@example.com"

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

- **HTTP 2xx**: Personal notification sent successfully ✅
- **HTTP 4xx/5xx**: Failed to send notification ❌

Report the result to the user with the HTTP status code.

## Integration with Other Skills

This skill can be combined with any workflow or agent that produces output for a specific person:

- **Triage reports**: A triage agent generates a summary, then this skill delivers it to the responsible person
- **Build/release notifications**: Notify a developer when their build completes or a release is published
- **Code review reminders**: Send a reminder to review a pending PR
- **Custom alerts**: Any agent or workflow can use this skill to deliver targeted messages

General flow:

1. An agent or workflow produces content to share
2. User requests "send personal notification" with recipient and message
3. This skill POSTs to the Logic App
4. Recipient receives a Teams message from the workflow bot
