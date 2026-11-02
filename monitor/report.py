import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = "xander-cage12/yandex-tracker-report-build"
GH = "https://api.github.com/repos/" + REPO
GL = "https://gitlab.3-bs.synology.me/api/v4/projects/21"
WORKFLOW = ".github/workflows/native-release.yml"
VERSION = "1.36.1"

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

OPENER = urllib.request.build_opener(NoRedirect)

def read_body(response):
    body = response.read(64 * 1024 * 1024 + 1)
    if len(body) > 64 * 1024 * 1024:
        raise RuntimeError("Response exceeds monitoring size limit")
    return body

def api(url, method="GET", data=None, optional=False, log_redirect=False):
    if url.startswith(GH + "/"):
        token = os.environ.get("GH_TOKEN", "")
        headers = {"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    elif url == GL or url.startswith(GL + "/"):
        token = os.environ.get("GITLAB_PUBLISH_TOKEN", "")
        headers = {"PRIVATE-TOKEN": token}
    else:
        raise RuntimeError("Unexpected API destination")
    if not token:
        raise RuntimeError("Monitoring secret is missing")
    if isinstance(data, dict):
        data = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    elif data is not None:
        headers["Content-Type"] = "application/octet-stream"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with OPENER.open(req, timeout=90) as response:
            return read_body(response)
    except urllib.error.HTTPError as error:
        if optional and error.code in (404, 410):
            return None
        if log_redirect and error.code in (301, 302, 303, 307, 308):
            destination = error.headers.get("Location", "")
            parsed = urllib.parse.urlsplit(destination)
            if parsed.scheme != "https" or parsed.username or parsed.password:
                raise RuntimeError("Unsafe log download redirect") from None
            with urllib.request.urlopen(urllib.request.Request(destination), timeout=90) as response:
                return read_body(response)
        raise RuntimeError("API HTTP status " + str(error.code)) from None

def get_json(url):
    return json.loads(api(url))

def redact(text):
    for key in ("GH_TOKEN", "GITLAB_READ_TOKEN", "GITLAB_PUBLISH_TOKEN"):
        value = os.environ.get(key, "")
        if value:
            text = text.replace(value, "[REDACTED]")
    text = re.sub(r"(?:glpat-|gh[pousr]_)[A-Za-z0-9_-]+", "[REDACTED]", text)
    return re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)

def managed_description(previous, block, begin, end):
    if begin not in previous or end not in previous:
        raise RuntimeError("Refusing to overwrite an unmanaged issue description")
    before, rest = previous.split(begin, 1)
    _, after = rest.split(end, 1)
    return before + block + after

def sync(run_id):
    run = get_json(GH + "/actions/runs/" + str(int(run_id)))
    if (run.get("head_repository") or {}).get("full_name") != REPO or run.get("head_branch") != "main":
        raise RuntimeError("Refusing to report a foreign repository or branch")
    if run.get("path", "").split("@", 1)[0] != WORKFLOW:
        raise RuntimeError("Unexpected source workflow")
    run_id, attempt = int(run["id"]), int(run["run_attempt"])
    jobs = get_json(GH + "/actions/runs/" + str(run_id) + "/jobs?filter=latest&per_page=100")
    snapshot = {"run": run, "jobs": jobs}
    version = str(run_id) + "-" + str(attempt) + "-" + os.environ["GITHUB_RUN_ID"] + "-" + os.environ["GITHUB_RUN_ATTEMPT"]
    package = GL + "/packages/generic/github-actions-monitor/" + version
    api(package + "/status.json", "PUT", redact(json.dumps(snapshot, indent=2)).encode())
    lines = ["Workflow: Native distributions to GitLab", "", "Run: " + run["html_url"],
             "Commit: `" + run["head_sha"] + "`", "Attempt: " + str(attempt),
             "Status: **" + run["status"] + " / " + str(run.get("conclusion")) + "**", "",
             "| Job | Status | Result | Failed steps |", "|---|---|---|---|"]
    for job in jobs["jobs"]:
        failed = [s["name"] for s in job.get("steps", []) if s.get("conclusion") == "failure"]
        cells = [job["name"], job["status"], str(job.get("conclusion")), "; ".join(failed) or "-"]
        cells = [redact(str(c)).replace("|", "\\|").replace("\n", " ") for c in cells]
        lines.append("| " + " | ".join(cells) + " |")
    if jobs.get("total_count", 0) > len(jobs["jobs"]):
        lines.append("\nJob table is truncated to the first 100 jobs.")
    lines += ["", "[Machine-readable snapshot](" + package + "/status.json)"]
    if run["status"] == "completed":
        try:
            logs = api(GH + "/actions/runs/" + str(run_id) + "/logs", optional=True, log_redirect=True)
            if logs is not None:
                api(package + "/actions-logs.zip", "PUT", logs)
                lines.append("[GitHub Actions log archive](" + package + "/actions-logs.zip)")
            else:
                lines.append("GitHub log archive is unavailable or expired.")
        except Exception:
            lines.append("GitHub log archive could not be transferred; status reporting remains available.")
    for target in ("windows-x64", "macos-x64", "macos-arm64"):
        log_url = GL + "/packages/generic/yandex-tracker-report/" + VERSION + "-" + str(run_id) + "-" + str(attempt) + "/diagnostics-" + target + ".log"
        raw = api(log_url, optional=True)
        if raw is not None:
            tail = "\n".join(redact(raw.decode("utf-8", errors="replace")).splitlines()[-100:])[-12000:]
            lines += ["", "### Private build diagnostics: " + target,
                      "[Complete private log](" + log_url + ")", "",
                      "\n".join("    " + line for line in tail.splitlines())]
    begin, end = "<!-- actions-monitor:" + str(run_id) + ":begin -->", "<!-- actions-monitor:" + str(run_id) + ":end -->"
    block = begin + "\n" + "\n".join(lines) + "\n" + end
    title = "GitHub native build #" + str(run["run_number"]) + " (run " + str(run_id) + ")"
    query = urllib.parse.urlencode({"scope": "all", "state": "all", "in": "title", "search": title, "per_page": 100})
    issues = get_json(GL + "/issues?" + query)
    existing = next((i for i in issues if i["title"] == title and begin in (i.get("description") or "") and end in (i.get("description") or "")), None)
    if existing:
        description = managed_description(existing["description"], block, begin, end)
        issue = json.loads(api(GL + "/issues/" + str(existing["iid"]), "PUT", {"description": description, "confidential": True}))
    else:
        issue = json.loads(api(GL + "/issues", "POST", {"title": title, "description": block, "confidential": True}))
    print("GitLab monitoring issue: " + issue["web_url"])

def main():
    if os.environ.get("GITHUB_REPOSITORY") != REPO:
        raise RuntimeError("Unexpected monitoring repository")
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    if os.environ["GITHUB_EVENT_NAME"] == "workflow_run":
        ids = [event["workflow_run"]["id"]]
    else:
        recent = get_json(GH + "/actions/workflows/native-release.yml/runs?branch=main&per_page=3")
        ids = [item["id"] for item in recent["workflow_runs"]]
    failures = 0
    for run_id in ids:
        try:
            sync(run_id)
        except Exception as error:
            failures += 1
            message = str(error) if isinstance(error, RuntimeError) else type(error).__name__
            print("Monitoring failed for run " + str(int(run_id)) + ": " + redact(message), file=sys.stderr)
    if not ids:
        print("No native workflow runs found")
    if failures:
        sys.exit(1)

if __name__ == "__main__":
    main()
