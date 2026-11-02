import ast
import hashlib
import io
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import time
import traceback
import urllib.error
import urllib.request
from pathlib import Path

API = "https://gitlab.3-bs.synology.me/api/v4/projects/21"
SOURCE = "a556df07f7b7c7765970eed8245e278a2696f9f8"
VERSION, BUILD = "1.36.1", "54"
TARGETS = ("windows-x64", "macos-x64", "macos-arm64")
ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "_private"
SRC = PRIVATE / "source"
LOG = PRIVATE / "build.log"
RUN = os.environ.get("GITHUB_RUN_ID", "0") + "-" + os.environ.get("GITHUB_RUN_ATTEMPT", "0")
PACKAGE = "/packages/generic/yandex-tracker-report/" + VERSION + "-" + RUN
CURRENT_STAGE = "initialization"

class ReleaseError(RuntimeError):
    pass

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

OPENER = urllib.request.build_opener(NoRedirect)

def request(path, token_name, method="GET", data=None, optional=False):
    token = os.environ.get(token_name, "")
    if not token:
        raise ReleaseError("Required GitLab secret is not configured")
    headers = {"PRIVATE-TOKEN": token}
    if isinstance(data, dict):
        data = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    elif data is not None:
        headers["Content-Type"] = "application/octet-stream"
    attempts = 3 if method in ("GET", "PUT") else 1
    for attempt in range(attempts):
        req = urllib.request.Request(API + path, data=data, headers=headers, method=method)
        try:
            with OPENER.open(req, timeout=180) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if optional and error.code == 404:
                return None
            retry = error.code in (429, 500, 502, 503, 504)
            if not retry or attempt + 1 == attempts:
                raise ReleaseError("GitLab HTTP status " + str(error.code) + " during " + method) from None
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            if attempt + 1 == attempts:
                raise ReleaseError("GitLab network request failed: " + type(error).__name__) from None
        print("Transient GitLab request failure; retry " + str(attempt + 2) + "/" + str(attempts), flush=True)
        time.sleep(2 ** attempt)

def read_json(path, token="GITLAB_READ_TOKEN", optional=False):
    raw = request(path, token, optional=optional)
    return None if raw is None else json.loads(raw)

def filename(target):
    suffix = ".zip" if target == "windows-x64" else ".tar.gz"
    return "YandexTrackerReport-" + VERSION + "-" + target + suffix

def upload(name, data):
    request(PACKAGE + "/" + name, "GITLAB_PUBLISH_TOKEN", "PUT", data)

def run(args, cwd=None, extra_env=None, timeout=900, stage="command"):
    global CURRENT_STAGE
    CURRENT_STAGE = stage
    print("Stage: " + stage, flush=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith("GITLAB_")}
    env.update(extra_env or {})
    try:
        result = subprocess.run([str(x) for x in args], cwd=cwd, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        with LOG.open("ab") as stream:
            stream.write(error.output or b"")
        raise ReleaseError(stage + " timed out") from None
    with LOG.open("ab") as stream:
        stream.write(result.stdout)
    if result.returncode:
        raise ReleaseError(stage + " failed with exit code " + str(result.returncode) + "; see private diagnostics")
    return result.stdout

def preflight():
    if read_json("/releases/v" + VERSION, optional=True) is not None:
        raise ReleaseError("Release already exists; refusing to overwrite")
    tag = read_json("/repository/tags/v" + VERSION, optional=True)
    if tag is not None and tag["commit"]["id"] != SOURCE:
        raise ReleaseError("Existing release tag points to a different commit")
    pipelines = read_json("/pipelines?sha=" + SOURCE + "&ref=main&per_page=1")
    if not pipelines or pipelines[0]["status"] != "success":
        raise ReleaseError("The latest GitLab pipeline for the pinned main commit must succeed first")
    read_json("", "GITLAB_PUBLISH_TOKEN")
    print("Preflight passed; release does not exist and pinned GitLab CI succeeded")

def fetch():
    archive = request("/repository/archive.tar.gz?sha=" + SOURCE, "GITLAB_READ_TOKEN")
    destination = PRIVATE / "download"
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as stream:
        if any(not (item.isfile() or item.isdir()) for item in stream.getmembers()):
            raise ReleaseError("Unexpected archive member type")
        stream.extractall(destination, filter="data")
    folders = list(destination.iterdir())
    if len(folders) != 1 or not folders[0].is_dir() or SRC.exists():
        raise ReleaseError("Unexpected source archive layout")
    folders[0].rename(SRC)
    values = {}
    for node in ast.parse((SRC / "tracker_core.py").read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign):
            for name in node.targets:
                if isinstance(name, ast.Name) and name.id in ("APP_VERSION", "APP_BUILD"):
                    values[name.id] = ast.literal_eval(node.value)
    if values != {"APP_VERSION": VERSION, "APP_BUILD": BUILD}:
        raise ReleaseError("Source version/build does not match release configuration")
    print("Pinned sources fetched privately and version checked")

def build(target):
    expected = "windows-x64" if sys.platform == "win32" else "macos-" + ("arm64" if platform.machine() == "arm64" else "x64")
    if target != expected or sys.platform not in ("win32", "darwin"):
        raise ReleaseError("Runner platform does not match target")
    run([sys.executable, "-m", "pip", "install", "-r", SRC / "requirements.txt", "pyinstaller==6.22.3"], stage="dependencies")
    run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], SRC, {"REQUIRE_GUI": "1"}, stage="source-tests")
    output = PRIVATE / "frozen"
    common = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--noupx",
              "--distpath", output, "--workpath", PRIVATE / "work", "--specpath", PRIVATE,
              "--paths", SRC, "--runtime-hook", ROOT / "ci/portable_hook.py"]
    run(common + ["--onefile", "--console", "--name", "YandexTrackerReportCLI", SRC / "tracker_report.py"], SRC, stage="package-cli")
    mode = "--onefile" if sys.platform == "win32" else "--onedir"
    run(common + [mode, "--windowed", "--name", "YandexTrackerReport", ROOT / "ci/gui_entry.py"], SRC, stage="package-gui")
    stage = PRIVATE / "YandexTrackerReport"
    stage.mkdir()
    if sys.platform == "win32":
        for name in ("YandexTrackerReport.exe", "YandexTrackerReportCLI.exe"):
            shutil.copy2(output / name, stage / name)
        for pattern in ("*.bat", "*.ps1"):
            for source in SRC.glob(pattern):
                shutil.copy2(source, stage / source.name)
        cli, gui = stage / "YandexTrackerReportCLI.exe", stage / "YandexTrackerReport.exe"
    else:
        shutil.copytree(output / "YandexTrackerReport.app", stage / "YandexTrackerReport.app", symlinks=True)
        shutil.copy2(output / "YandexTrackerReportCLI", stage / "YandexTrackerReportCLI")
        cli = stage / "YandexTrackerReportCLI"
        gui = stage / "YandexTrackerReport.app/Contents/MacOS/YandexTrackerReport"
    if VERSION.encode() not in run([cli, "--version"], stage, timeout=120, stage="smoke-cli-version"):
        raise ReleaseError("Frozen CLI version check failed")
    run([cli, "--help"], stage, timeout=120, stage="smoke-cli-help")
    run([gui], stage, {"YTR_BUILD_SMOKE_TEST": "1"}, timeout=120, stage="smoke-gui")
    for folder in ("config", "logs"):
        shutil.rmtree(stage / folder, ignore_errors=True)
        (stage / folder).mkdir()
    info = {"version": VERSION, "build": BUILD, "source_sha": SOURCE, "target": target,
            "workflow_sha": os.environ.get("GITHUB_SHA"), "run": RUN,
            "python": sys.version, "os": platform.platform(),
            "dependencies": run([sys.executable, "-m", "pip", "freeze"], stage="dependency-manifest").decode("utf-8", errors="replace"),
            "verification": "Source unittest, frozen CLI --version/--help, frozen GUI startup and exit",
            "signing": "No Windows publisher signature; macOS ad-hoc only, not notarized"}
    (stage / "BUILD-INFO.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    (stage / "INSTALL.txt").write_text(
        "Extract the entire archive into a writable folder. Python is bundled.\n"
        "Launch YandexTrackerReport.exe (Windows) or YandexTrackerReport.app (macOS).\n"
        "The CLI is YandexTrackerReportCLI[.exe]; use --help.\n"
        "Portable config/logs are outside the app bundle; a per-user fallback is used if needed.\n"
        "No trusted publisher signature or Apple notarization. OS security warnings may occur.\n"
        "No security settings are disabled automatically. No real Tracker API export was tested.\n",
        encoding="utf-8")
    archive = PRIVATE / filename(target)
    if target == "windows-x64":
        shutil.make_archive(str(archive.with_suffix("")), "zip", PRIVATE, stage.name)
    else:
        with tarfile.open(archive, "w:gz") as stream:
            stream.add(stage, arcname=stage.name)
    info.update({"file": archive.name, "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(), "size": archive.stat().st_size})
    (PRIVATE / (target + ".json")).write_text(json.dumps(info), encoding="utf-8")
    print("Native build and smoke tests passed: " + target)

def upload_build(target):
    info = json.loads((PRIVATE / (target + ".json")).read_text(encoding="utf-8"))
    upload(info["file"], (PRIVATE / info["file"]).read_bytes())
    upload(target + ".json", json.dumps(info).encode())
    print("Binary and manifest uploaded to GitLab: " + target)

def diagnostics(target):
    if LOG.is_file():
        upload("diagnostics-" + target + ".log", LOG.read_bytes())
        print("Private diagnostic log uploaded to the GitLab package registry")

def release():
    preflight()
    manifests = []
    for target in TARGETS:
        info = read_json(PACKAGE + "/" + target + ".json")
        if (info["source_sha"], info["version"], info["build"], info["target"], info["run"], info["file"]) != (SOURCE, VERSION, BUILD, target, RUN, filename(target)):
            raise ReleaseError("Build manifest mismatch")
        data = request(PACKAGE + "/" + info["file"], "GITLAB_READ_TOKEN")
        if len(data) != info["size"] or hashlib.sha256(data).hexdigest() != info["sha256"]:
            raise ReleaseError("Uploaded binary checksum mismatch")
        manifests.append(info)
    sums = "".join(item["sha256"] + "  " + item["file"] + "\n" for item in manifests)
    upload("SHA256SUMS", sums.encode())
    upload("BUILD-MANIFEST.json", json.dumps(manifests, indent=2).encode())
    names = [item["file"] for item in manifests] + ["SHA256SUMS", "BUILD-MANIFEST.json"]
    links = [{"name": name, "url": API + PACKAGE + "/" + name, "link_type": "package"} for name in names]
    description = (
        "Native Windows x64, macOS Intel and macOS Apple Silicon distributions.\n\n"
        "Source commit: `" + SOURCE + "`; application build: " + BUILD + ".\n\n"
        "All three builds passed source tests and frozen CLI/GUI smoke tests; uploaded SHA-256 hashes verified.\n\n"
        "Windows binaries are unsigned. macOS apps use ad-hoc signing and are not notarized. "
        "OS warnings may occur. Real Tracker API exports and full desktop workflows were not tested.\n\n"
        "Packaging runtime hook keeps config/logs outside temporary extraction folders and signed app bundles."
    )
    request("/releases", "GITLAB_PUBLISH_TOKEN", "POST", {
        "name": "Yandex Tracker Report " + VERSION, "tag_name": "v" + VERSION,
        "ref": SOURCE, "description": description, "assets": {"links": links}})
    print("GitLab release v" + VERSION + " published with three distributions and checksums")

if __name__ == "__main__":
    PRIVATE.mkdir(parents=True, exist_ok=True)
    try:
        mode = sys.argv[1]
        CURRENT_STAGE = mode
        target = os.environ.get("TARGET", "")
        if mode in ("build", "upload", "diagnostics") and target not in TARGETS:
            raise ReleaseError("Invalid build target")
        if mode == "preflight": preflight()
        elif mode == "fetch": fetch()
        elif mode == "build": build(target)
        elif mode == "upload": upload_build(target)
        elif mode == "diagnostics": diagnostics(target)
        elif mode == "release": release()
        else: raise ReleaseError("Unknown operation")
    except Exception as error:
        with LOG.open("a", encoding="utf-8") as stream:
            traceback.print_exc(file=stream)
        detail = str(error) if isinstance(error, ReleaseError) else type(error).__name__
        print("Operation failed at " + CURRENT_STAGE + ": " + detail + ". Private logs remain in GitLab diagnostics.", file=sys.stderr)
        sys.exit(1)
