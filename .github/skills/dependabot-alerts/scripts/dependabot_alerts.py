#!/usr/bin/env python3
"""GitHub Dependabot Alerts API client.

Usage:
    python dependabot_alerts.py <owner/repo> <command> [options]

Commands:
    list-alerts      List Dependabot alerts
    get-alert        Get a specific alert by number
    update-alert     Dismiss or reopen an alert

Environment:
    GITHUB_TOKEN  - Required for private repos. Falls back to `gh auth token`.

Examples:
    python dependabot_alerts.py microsoft/vscode-gradle list-alerts --state open
    python dependabot_alerts.py microsoft/vscode-gradle list-alerts --severity critical --ecosystem npm
    python dependabot_alerts.py microsoft/vscode-gradle get-alert 42
    python dependabot_alerts.py microsoft/vscode-gradle update-alert 42 --state dismissed --reason tolerable_risk
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
    m = re.match(r"https?://github\.com/([^/]+/[^/]+)", repo_str)
    if m:
        return m.group(1).rstrip("/")
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
        "ecosystem": args.ecosystem,
        "scope": args.scope,
        "sort": args.sort,
        "direction": args.direction,
        "per_page": args.per_page,
        "before": args.before,
        "after": args.after,
    }
    qs = build_query_string(params)
    path = f"/repos/{repo}/dependabot/alerts"
    if qs:
        path += f"?{qs}"

    alerts = api_request("GET", path, token)
    if not alerts:
        print("No Dependabot alerts found.")
        return

    print(f"Found {len(alerts)} alert(s):\n")
    print(f"{'#':<6} {'State':<15} {'Severity':<10} {'Package':<35} {'Ecosystem':<12} {'Manifest':<40} {'Created'}")
    print("-" * 140)
    for a in alerts:
        num = a["number"]
        state = a["state"]
        vuln = a.get("security_vulnerability", {})
        severity = vuln.get("severity", "?")
        pkg = vuln.get("package", {})
        pkg_name = pkg.get("name", "?")
        ecosystem = pkg.get("ecosystem", "?")
        dep = a.get("dependency", {})
        manifest = dep.get("manifest_path", "?")
        created = a.get("created_at", "?")[:10]
        print(f"{num:<6} {state:<15} {severity:<10} {pkg_name:<35} {ecosystem:<12} {manifest:<40} {created}")


def cmd_get_alert(repo: str, token: str | None, args: argparse.Namespace):
    alert_number = args.alert_number
    path = f"/repos/{repo}/dependabot/alerts/{alert_number}"
    a = api_request("GET", path, token)

    vuln = a.get("security_vulnerability", {})
    pkg = vuln.get("package", {})
    dep = a.get("dependency", {})
    advisory = a.get("security_advisory", {})

    print(f"Alert #{a['number']}")
    print(f"  State:              {a['state']}")
    print(f"  Package:            {pkg.get('name', '?')} ({pkg.get('ecosystem', '?')})")
    print(f"  Manifest:           {dep.get('manifest_path', '?')}")
    print(f"  Scope:              {dep.get('scope', '?')}")
    print(f"  Vulnerable range:   {vuln.get('vulnerable_version_range', '?')}")
    print(f"  Patched version:    {vuln.get('first_patched_version', {}).get('identifier', 'no patch available')}")
    print(f"  Severity:           {vuln.get('severity', '?')}")
    print(f"  Created:            {a.get('created_at', '?')}")
    print(f"  Updated:            {a.get('updated_at', '?')}")
    print(f"  URL:                {a.get('html_url', '?')}")

    if a.get("dismissed_by"):
        print(f"  Dismissed by:       {a['dismissed_by'].get('login', '?')}")
        print(f"  Dismissed reason:   {a.get('dismissed_reason', '?')}")
        print(f"  Dismissed at:       {a.get('dismissed_at', '?')}")
        if a.get("dismissed_comment"):
            print(f"  Dismissed comment:  {a['dismissed_comment']}")

    if a.get("auto_dismissed_at"):
        print(f"  Auto-dismissed at:  {a['auto_dismissed_at']}")

    # Advisory details
    if advisory:
        print(f"\n  Advisory:")
        print(f"    GHSA ID:      {advisory.get('ghsa_id', '?')}")
        print(f"    CVE ID:       {advisory.get('cve_id', '?')}")
        print(f"    Summary:      {advisory.get('summary', '?')}")
        print(f"    CVSS score:   {advisory.get('cvss', {}).get('score', '?')} ({advisory.get('cvss', {}).get('vector_string', '')})")
        print(f"    Published:    {advisory.get('published_at', '?')[:10] if advisory.get('published_at') else '?'}")
        print(f"    Updated:      {advisory.get('updated_at', '?')[:10] if advisory.get('updated_at') else '?'}")

        cwes = advisory.get("cwes", [])
        if cwes:
            cwe_strs = [f"{c.get('cwe_id', '?')} ({c.get('name', '')})" for c in cwes]
            print(f"    CWEs:         {', '.join(cwe_strs)}")

        refs = advisory.get("references", [])
        if refs:
            print(f"    References:")
            for ref in refs[:5]:
                print(f"      - {ref.get('url', '?')}")

        desc = advisory.get("description", "")
        if desc:
            print(f"\n  Description:\n{_indent(desc, 4)}")


def cmd_update_alert(repo: str, token: str | None, args: argparse.Namespace):
    alert_number = args.alert_number
    body: dict = {"state": args.state}

    if args.state == "dismissed":
        if not args.reason:
            print("Error: --reason is required when dismissing an alert.", file=sys.stderr)
            print("  Valid reasons: fix_started, inaccurate, no_bandwidth, not_used, tolerable_risk", file=sys.stderr)
            sys.exit(1)
        body["dismissed_reason"] = args.reason
        if args.comment:
            body["dismissed_comment"] = args.comment

    path = f"/repos/{repo}/dependabot/alerts/{alert_number}"
    result = api_request("PATCH", path, token, body)
    print(f"Alert #{result['number']} updated to state: {result['state']}")
    if result.get("dismissed_reason"):
        print(f"  Reason: {result['dismissed_reason']}")


# ── Helpers ─────────────────────────────────────────────────────────


def _indent(text: str, spaces: int) -> str:
    prefix = " " * spaces
    return "\n".join(prefix + line for line in text.splitlines())


# ── CLI ─────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="GitHub Dependabot Alerts API client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("repo", help="Repository in owner/repo format or GitHub URL")

    sub = parser.add_subparsers(dest="command", required=True)

    # list-alerts
    p = sub.add_parser("list-alerts", help="List Dependabot alerts")
    p.add_argument("--state", choices=["open", "dismissed", "fixed", "auto_dismissed"])
    p.add_argument("--severity", choices=["critical", "high", "medium", "low"])
    p.add_argument("--ecosystem", help="Package ecosystem (npm, maven, pip, nuget, etc.)")
    p.add_argument("--scope", choices=["runtime", "development"])
    p.add_argument("--sort", choices=["created", "updated"], default="created")
    p.add_argument("--direction", choices=["asc", "desc"], default="desc")
    p.add_argument("--per-page", dest="per_page", type=int, default=30)
    p.add_argument("--before", help="Cursor for previous page (from response headers)")
    p.add_argument("--after", help="Cursor for next page (from response headers)")

    # get-alert
    p = sub.add_parser("get-alert", help="Get a specific alert")
    p.add_argument("alert_number", type=int, help="Alert number")

    # update-alert
    p = sub.add_parser("update-alert", help="Dismiss or reopen an alert")
    p.add_argument("alert_number", type=int, help="Alert number")
    p.add_argument("--state", required=True, choices=["dismissed", "open"])
    p.add_argument("--reason", choices=["fix_started", "inaccurate", "no_bandwidth", "not_used", "tolerable_risk"],
                   help="Dismissal reason (required when --state dismissed)")
    p.add_argument("--comment", help="Optional dismissal comment")

    args = parser.parse_args()
    repo = parse_repo(args.repo)
    token = get_github_token()

    if not token:
        print("Warning: No GitHub token found. API calls may fail for private repos.", file=sys.stderr)
        print("Set GITHUB_TOKEN or install GitHub CLI (gh).", file=sys.stderr)

    commands = {
        "list-alerts": cmd_list_alerts,
        "get-alert": cmd_get_alert,
        "update-alert": cmd_update_alert,
    }

    commands[args.command](repo, token, args)


if __name__ == "__main__":
    main()
