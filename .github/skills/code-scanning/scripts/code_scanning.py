#!/usr/bin/env python3
"""GitHub Code Scanning API client.

Usage:
    python code_scanning.py <owner/repo> <command> [options]

Commands:
    list-alerts      List code scanning alerts
    get-alert        Get a specific alert by number
    list-instances   List instances (locations) for an alert
    update-alert     Dismiss or reopen an alert
    list-analyses    List CodeQL analyses (scan runs)
    get-analysis     Get a specific analysis by ID

Environment:
    GITHUB_TOKEN  - Required for private repos. Falls back to `gh auth token`.

Examples:
    python code_scanning.py microsoft/vscode-gradle list-alerts --state open
    python code_scanning.py microsoft/vscode-gradle get-alert 42
    python code_scanning.py microsoft/vscode-gradle list-instances 42
    python code_scanning.py microsoft/vscode-gradle update-alert 42 --state dismissed --reason "false positive"
    python code_scanning.py microsoft/vscode-gradle list-analyses --ref refs/heads/main
    python code_scanning.py microsoft/vscode-gradle get-analysis 12345
"""

import argparse
import io
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

# Ensure stdout handles Unicode on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

API_BASE = "https://api.github.com"


def get_github_token() -> str | None:
    """Get GitHub token from env var or gh CLI."""
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        return token
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def api_request(method: str, path: str, token: str | None, body: dict | None = None) -> dict | list:
    """Make a GitHub API request. Returns parsed JSON."""
    url = f"{API_BASE}{path}"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        print(f"HTTP {e.code} {e.reason}: {error_body}", file=sys.stderr)
        sys.exit(1)


def parse_repo(repo_str: str) -> str:
    """Parse owner/repo from a string or GitHub URL."""
    # Handle URLs like https://github.com/owner/repo/...
    m = re.match(r"https?://github\.com/([^/]+/[^/]+)", repo_str)
    if m:
        return m.group(1).rstrip("/")
    # Direct owner/repo
    if "/" in repo_str:
        return repo_str
    print(f"Error: Cannot parse repo from '{repo_str}'. Use owner/repo format.", file=sys.stderr)
    sys.exit(1)


def build_query_string(params: dict) -> str:
    """Build URL query string from a dict, skipping None values."""
    parts = []
    for k, v in params.items():
        if v is not None:
            parts.append(f"{urllib.request.quote(k)}={urllib.request.quote(str(v))}")
    return "&".join(parts)


# ── Commands ────────────────────────────────────────────────────────


def cmd_list_alerts(repo: str, token: str | None, args: argparse.Namespace):
    params = {
        "state": args.state,
        "severity": args.severity,
        "tool_name": args.tool_name,
        "ref": args.ref,
        "per_page": args.per_page,
        "page": args.page,
    }
    qs = build_query_string(params)
    path = f"/repos/{repo}/code-scanning/alerts"
    if qs:
        path += f"?{qs}"

    alerts = api_request("GET", path, token)
    if not alerts:
        print("No code scanning alerts found.")
        return

    print(f"Found {len(alerts)} alert(s):\n")
    print(f"{'#':<6} {'State':<12} {'Severity':<10} {'Rule':<40} {'File':<50} {'Created'}")
    print("-" * 140)
    for a in alerts:
        num = a["number"]
        state = a["state"]
        rule = a.get("rule", {})
        rule_id = rule.get("id", "?")
        severity = rule.get("security_severity_level") or rule.get("severity", "?")
        location = a.get("most_recent_instance", {}).get("location", {})
        fpath = location.get("path", "?")
        line = location.get("start_line", "?")
        created = a.get("created_at", "?")[:10]
        print(f"{num:<6} {state:<12} {severity:<10} {rule_id:<40} {fpath}:{line:<48} {created}")


def cmd_get_alert(repo: str, token: str | None, args: argparse.Namespace):
    alert_number = args.alert_number
    path = f"/repos/{repo}/code-scanning/alerts/{alert_number}"
    alert = api_request("GET", path, token)

    rule = alert.get("rule", {})
    instance = alert.get("most_recent_instance", {})
    location = instance.get("location", {})

    print(f"Alert #{alert['number']}")
    print(f"  State:       {alert['state']}")
    print(f"  Rule:        {rule.get('id', '?')} — {rule.get('description', '?')}")
    print(f"  Severity:    {rule.get('security_severity_level') or rule.get('severity', '?')}")
    print(f"  Tool:        {alert.get('tool', {}).get('name', '?')} {alert.get('tool', {}).get('version', '')}")
    print(f"  File:        {location.get('path', '?')}:{location.get('start_line', '?')}-{location.get('end_line', '?')}")
    print(f"  Created:     {alert.get('created_at', '?')}")
    print(f"  Updated:     {alert.get('updated_at', '?')}")
    print(f"  URL:         {alert.get('html_url', '?')}")

    if alert.get("dismissed_by"):
        print(f"  Dismissed by: {alert['dismissed_by'].get('login', '?')}")
        print(f"  Dismissed reason: {alert.get('dismissed_reason', '?')}")
        print(f"  Dismissed at: {alert.get('dismissed_at', '?')}")

    # Message from the most recent instance
    msg = instance.get("message", {}).get("text", "")
    if msg:
        print(f"\n  Message:\n    {msg}")

    # Rule help text (markdown) — useful for AI fixing
    help_text = rule.get("help", "")
    if help_text:
        print(f"\n  Rule Help:\n{_indent(help_text, 4)}")
    elif rule.get("help_uri"):
        print(f"\n  Rule Help URI: {rule['help_uri']}")


def cmd_list_instances(repo: str, token: str | None, args: argparse.Namespace):
    alert_number = args.alert_number
    params = {
        "ref": args.ref,
        "per_page": args.per_page,
        "page": args.page,
    }
    qs = build_query_string(params)
    path = f"/repos/{repo}/code-scanning/alerts/{alert_number}/instances"
    if qs:
        path += f"?{qs}"

    instances = api_request("GET", path, token)
    if not instances:
        print(f"No instances found for alert #{alert_number}.")
        return

    print(f"Found {len(instances)} instance(s) for alert #{alert_number}:\n")
    print(f"{'#':<4} {'Ref':<30} {'File':<50} {'Lines':<12} {'State':<12} {'Message'}")
    print("-" * 140)
    for i, inst in enumerate(instances, 1):
        loc = inst.get("location", {})
        fpath = loc.get("path", "?")
        start = loc.get("start_line", "?")
        end = loc.get("end_line", "?")
        ref = inst.get("ref", "?")
        state = inst.get("state", "?")
        msg = inst.get("message", {}).get("text", "")[:60]
        print(f"{i:<4} {ref:<30} {fpath:<50} {start}-{end:<9} {state:<12} {msg}")


def cmd_update_alert(repo: str, token: str | None, args: argparse.Namespace):
    alert_number = args.alert_number
    body: dict = {"state": args.state}

    if args.state == "dismissed":
        if not args.reason:
            print("Error: --reason is required when dismissing an alert.", file=sys.stderr)
            print("  Valid reasons: 'false positive', \"won't fix\", 'used in tests'", file=sys.stderr)
            sys.exit(1)
        body["dismissed_reason"] = args.reason
        if args.comment:
            body["dismissed_comment"] = args.comment

    path = f"/repos/{repo}/code-scanning/alerts/{alert_number}"
    result = api_request("PATCH", path, token, body)
    print(f"Alert #{result['number']} updated to state: {result['state']}")
    if result.get("dismissed_reason"):
        print(f"  Reason: {result['dismissed_reason']}")


def cmd_list_analyses(repo: str, token: str | None, args: argparse.Namespace):
    params = {
        "tool_name": args.tool_name,
        "ref": args.ref,
        "per_page": args.per_page,
        "page": args.page,
    }
    qs = build_query_string(params)
    path = f"/repos/{repo}/code-scanning/analyses"
    if qs:
        path += f"?{qs}"

    analyses = api_request("GET", path, token)
    if not analyses:
        print("No analyses found.")
        return

    print(f"Found {len(analyses)} analysis/analyses:\n")
    print(f"{'ID':<12} {'Tool':<20} {'Ref':<30} {'Commit':<12} {'Created':<22} {'Alerts'}")
    print("-" * 120)
    for a in analyses:
        aid = a["id"]
        tool = a.get("tool", {}).get("name", "?")
        ref = a.get("ref", "?")
        sha = a.get("commit_sha", "?")[:10]
        created = a.get("created_at", "?")[:19]
        # results_count is total alerts at time of analysis
        results = a.get("results_count", "?")
        print(f"{aid:<12} {tool:<20} {ref:<30} {sha:<12} {created:<22} {results}")


def cmd_get_analysis(repo: str, token: str | None, args: argparse.Namespace):
    analysis_id = args.analysis_id
    path = f"/repos/{repo}/code-scanning/analyses/{analysis_id}"
    a = api_request("GET", path, token)

    print(f"Analysis #{a['id']}")
    print(f"  Tool:        {a.get('tool', {}).get('name', '?')} {a.get('tool', {}).get('version', '')}")
    print(f"  Ref:         {a.get('ref', '?')}")
    print(f"  Commit:      {a.get('commit_sha', '?')}")
    print(f"  Created:     {a.get('created_at', '?')}")
    print(f"  Results:     {a.get('results_count', '?')} total alerts")
    print(f"  Category:    {a.get('category', '?')}")
    print(f"  Sarif ID:    {a.get('sarif_id', '?')}")
    print(f"  URL:         {a.get('url', '?')}")


# ── Helpers ─────────────────────────────────────────────────────────


def _indent(text: str, spaces: int) -> str:
    prefix = " " * spaces
    return "\n".join(prefix + line for line in text.splitlines())


# ── CLI ─────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="GitHub Code Scanning API client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("repo", help="Repository in owner/repo format or GitHub URL")

    sub = parser.add_subparsers(dest="command", required=True)

    # list-alerts
    p = sub.add_parser("list-alerts", help="List code scanning alerts")
    p.add_argument("--state", choices=["open", "dismissed", "fixed"])
    p.add_argument("--severity", choices=["critical", "high", "medium", "low", "warning", "note", "error"])
    p.add_argument("--tool-name", dest="tool_name")
    p.add_argument("--ref")
    p.add_argument("--per-page", dest="per_page", type=int, default=30)
    p.add_argument("--page", type=int, default=1)

    # get-alert
    p = sub.add_parser("get-alert", help="Get a specific alert")
    p.add_argument("alert_number", type=int, help="Alert number")

    # list-instances
    p = sub.add_parser("list-instances", help="List instances of an alert")
    p.add_argument("alert_number", type=int, help="Alert number")
    p.add_argument("--ref")
    p.add_argument("--per-page", dest="per_page", type=int, default=30)
    p.add_argument("--page", type=int, default=1)

    # update-alert
    p = sub.add_parser("update-alert", help="Dismiss or reopen an alert")
    p.add_argument("alert_number", type=int, help="Alert number")
    p.add_argument("--state", required=True, choices=["dismissed", "open"])
    p.add_argument("--reason", help="Dismissal reason: 'false positive', \"won't fix\", 'used in tests'")
    p.add_argument("--comment", help="Optional dismissal comment")

    # list-analyses
    p = sub.add_parser("list-analyses", help="List CodeQL analyses")
    p.add_argument("--tool-name", dest="tool_name")
    p.add_argument("--ref")
    p.add_argument("--per-page", dest="per_page", type=int, default=30)
    p.add_argument("--page", type=int, default=1)

    # get-analysis
    p = sub.add_parser("get-analysis", help="Get a specific analysis")
    p.add_argument("analysis_id", type=int, help="Analysis ID")

    args = parser.parse_args()
    repo = parse_repo(args.repo)
    token = get_github_token()

    if not token:
        print("Warning: No GitHub token found. API calls may fail for private repos.", file=sys.stderr)
        print("Set GITHUB_TOKEN or install GitHub CLI (gh).", file=sys.stderr)

    commands = {
        "list-alerts": cmd_list_alerts,
        "get-alert": cmd_get_alert,
        "list-instances": cmd_list_instances,
        "update-alert": cmd_update_alert,
        "list-analyses": cmd_list_analyses,
        "get-analysis": cmd_get_analysis,
    }

    commands[args.command](repo, token, args)


if __name__ == "__main__":
    main()
