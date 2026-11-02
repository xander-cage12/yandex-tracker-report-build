import hashlib
import json
import os
import sys
import tarfile
import time
import traceback
import zipfile
import release as base

base.SOURCE = "3d914a0e1a1dc9d85b032567bf44ce850c0abafb"
base.VERSION, base.BUILD = "1.36.2", "55"
base.PACKAGE = "/packages/generic/yandex-tracker-report/" + base.VERSION + "-" + base.RUN
TAG = "v" + base.VERSION

def filename(target):
    suffix = ".zip" if target == "windows-x64" else ".tar.gz"
    return "YandexTrackerReport-" + base.VERSION + "-build" + base.BUILD + "-" + target + suffix

base.filename = filename

def preflight():
    if base.read_json("/releases/" + TAG, optional=True) is not None:
        raise base.ReleaseError("Release already exists; refusing to overwrite")
    tag = base.read_json("/repository/tags/" + TAG, optional=True)
    if tag is not None and tag["commit"]["id"] != base.SOURCE:
        raise base.ReleaseError("Existing release tag points to a different commit")
    base.read_json("", "GITLAB_PUBLISH_TOKEN")
    deadline = time.monotonic() + 1800
    while True:
        pipelines = base.read_json("/pipelines?sha=" + base.SOURCE + "&ref=main&per_page=1")
        status = pipelines[0]["status"] if pipelines else "not-created"
        if status == "success":
            break
        if status in ("failed", "canceled", "skipped", "manual"):
            raise base.ReleaseError("Pinned GitLab CI cannot release: " + status)
        if time.monotonic() >= deadline:
            raise base.ReleaseError("Timed out waiting for pinned GitLab CI")
        print("Waiting for pinned GitLab CI: " + status, flush=True)
        time.sleep(20)
    print("Release 1.36.2 preflight passed")

def build(target):
    base.build(target)
    base.CURRENT_STAGE = "release-support-files"
    stage = base.PRIVATE / "YandexTrackerReport"
    helpers = ["TRUST_AND_SECURITY.md", "BUILDING.md"]
    if target == "windows-x64":
        helpers.append("prepare_windows.ps1")
        executables = ["YandexTrackerReport.exe", "YandexTrackerReportCLI.exe"]
        for name in ("sign_scripts.bat", "sign_scripts.ps1", "unblock_files.bat", "unblock_files.ps1"):
            (stage / name).unlink(missing_ok=True)
    else:
        helpers.append("prepare_macos.command")
        executables = ["YandexTrackerReport.app/Contents/MacOS/YandexTrackerReport", "YandexTrackerReportCLI"]
    for name in helpers:
        base.shutil.copy2(base.SRC / name, stage / name)
    if target != "windows-x64":
        (stage / "prepare_macos.command").chmod(0o755)
    sums = "".join(hashlib.sha256((stage / name).read_bytes()).hexdigest() + "  " + name + "\n" for name in executables)
    (stage / "BINARY_SHA256SUMS").write_text(sums, encoding="ascii", newline="\n")
    if target == "windows-x64":
        base.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-File", stage / "prepare_windows.ps1", "-WhatIf"], stage, timeout=120, stage="helper-windows-dry-run")
    else:
        base.run(["/bin/sh", "-n", stage / "prepare_macos.command"], stage, stage="helper-macos-syntax")
        base.run(["/usr/bin/codesign", "--verify", "--deep", "--strict", stage / "YandexTrackerReport.app"], stage, stage="helper-macos-app-integrity")
        base.run(["/usr/bin/codesign", "--verify", "--strict", stage / "YandexTrackerReportCLI"], stage, stage="helper-macos-cli-integrity")
    info_path = base.PRIVATE / (target + ".json")
    info = json.loads(info_path.read_text(encoding="utf-8"))
    for field in ("sha256", "size"):
        info.pop(field, None)
    info.update({"release_tag": TAG, "support_files": helpers + ["BINARY_SHA256SUMS"],
                 "support_verification": "Windows helper -WhatIf; macOS shell syntax and code-signature integrity. No unblocking executed."})
    (stage / "BUILD-INFO.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    base.CURRENT_STAGE = "archive-release"
    archive = base.PRIVATE / filename(target)
    required = [stage.name + "/" + name for name in helpers + ["BINARY_SHA256SUMS"]]
    if target == "windows-x64":
        base.shutil.make_archive(str(archive.with_suffix("")), "zip", base.PRIVATE, stage.name)
        with zipfile.ZipFile(archive) as stream:
            if stream.testzip() is not None or any(name not in stream.namelist() for name in required):
                raise base.ReleaseError("ZIP integrity/support files check failed")
    else:
        with tarfile.open(archive, "w:gz") as stream:
            stream.add(stage, arcname=stage.name)
        with tarfile.open(archive, "r:gz") as stream:
            if any(name not in stream.getnames() for name in required):
                raise base.ReleaseError("TAR support files check failed")
    info.update({"file": archive.name, "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(), "size": archive.stat().st_size})
    info_path.write_text(json.dumps(info), encoding="utf-8")
    print("Release package and helper checks passed: " + target)

def publish():
    preflight()
    manifests = []
    for target in base.TARGETS:
        info = base.read_json(base.PACKAGE + "/" + target + ".json")
        expected = (base.SOURCE, base.VERSION, base.BUILD, target, base.RUN, filename(target), TAG)
        actual = (info["source_sha"], info["version"], info["build"], info["target"], info["run"], info["file"], info.get("release_tag"))
        helper = "prepare_windows.ps1" if target == "windows-x64" else "prepare_macos.command"
        if actual != expected or not {helper, "TRUST_AND_SECURITY.md", "BUILDING.md", "BINARY_SHA256SUMS"}.issubset(info.get("support_files", [])):
            raise base.ReleaseError("Release manifest or helper coverage mismatch")
        data = base.request(base.PACKAGE + "/" + info["file"], "GITLAB_READ_TOKEN")
        if len(data) != info["size"] or hashlib.sha256(data).hexdigest() != info["sha256"]:
            raise base.ReleaseError("Uploaded release checksum mismatch")
        manifests.append(info)
    sums = "".join(info["sha256"] + "  " + info["file"] + "\n" for info in manifests)
    base.upload("SHA256SUMS", sums.encode())
    base.upload("BUILD-MANIFEST.json", json.dumps(manifests, indent=2).encode())
    names = [info["file"] for info in manifests] + ["SHA256SUMS", "BUILD-MANIFEST.json"]
    links = [{"name": name, "url": base.API + base.PACKAGE + "/" + name, "link_type": "package"} for name in names]
    description = (
        "Yandex Tracker Report " + base.VERSION + ", build " + base.BUILD + ".\n\nSource: `" + base.SOURCE + "`.\n\n"
        "Native Windows x64, macOS Intel and Apple Silicon builds passed source tests, frozen CLI/GUI smoke tests and uploaded SHA-256 verification. "
        "Archives include the platform first-run helper, BINARY_SHA256SUMS, TRUST_AND_SECURITY.md and BUILDING.md. "
        "Windows helper was checked with -WhatIf; macOS helper syntax and code-signature integrity were checked.\n\n"
        "Helpers require exact UNBLOCK confirmation and checksum checks. They do not run automatically, install certificates or change global policies/antivirus exclusions. "
        "Windows removes download metadata only from the two EXEs; macOS removes quarantine only from the bundle root and CLI, without recursion.\n\n"
        "Windows remains unsigned; macOS uses ad-hoc signing, not Developer ID/notarization. OS warnings can remain. "
        "Checksums do not authenticate a publisher. Real Tracker exports/full desktop workflows were not tested. Existing v1.36.1 was not replaced."
    )
    base.request("/releases", "GITLAB_PUBLISH_TOKEN", "POST", {
        "name": "Yandex Tracker Report " + base.VERSION + " build " + base.BUILD,
        "tag_name": TAG, "ref": base.SOURCE, "description": description, "assets": {"links": links}})
    print("Published GitLab release " + TAG)

if __name__ == "__main__":
    base.PRIVATE.mkdir(parents=True, exist_ok=True)
    try:
        mode = sys.argv[1]
        base.CURRENT_STAGE = mode
        target = os.environ.get("TARGET", "")
        if mode in ("build", "upload", "diagnostics") and target not in base.TARGETS:
            raise base.ReleaseError("Invalid build target")
        if mode == "preflight": preflight()
        elif mode == "fetch": base.fetch()
        elif mode == "build": build(target)
        elif mode == "upload": base.upload_build(target)
        elif mode == "diagnostics": base.diagnostics(target)
        elif mode == "release": publish()
        else: raise base.ReleaseError("Unknown operation")
    except Exception as error:
        with base.LOG.open("a", encoding="utf-8") as stream:
            traceback.print_exc(file=stream)
        detail = str(error) if isinstance(error, base.ReleaseError) else type(error).__name__
        print("Release failed at " + base.CURRENT_STAGE + ": " + detail + "; private details remain in GitLab diagnostics.", file=sys.stderr)
        sys.exit(1)
