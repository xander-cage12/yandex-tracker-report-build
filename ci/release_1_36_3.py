"""Нативный выпуск 1.36.3 со строгими тестами и встроенными иконками."""
import importlib.util
import json
import os
import plistlib
import sys
import traceback
import release_1_36_2 as legacy

base = legacy.base
base.SOURCE = "f5c29ec46435f255fb1da88a55c0ede96b4468c2"
base.VERSION, base.BUILD = "1.36.3", "56"
base.PACKAGE = "/packages/generic/yandex-tracker-report/" + base.VERSION + "-" + base.RUN
legacy.TAG = "v" + base.VERSION
ORIGINAL_RUN, ORIGINAL_REQUEST = base.run, base.request
ICONS = base.PRIVATE / "icons"
RESULTS = base.PRIVATE / "test-results.json"


def load_icons():
    spec = importlib.util.spec_from_file_location("release_icons", base.SRC / "scripts/app_icons.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_icon(path):
    icons = load_icons()
    if sys.platform == "win32":
        import pefile
        expected = {icons.png(n) for n in (16, 32, 48, 64, 128, 256)}
        found, group = set(), False
        with pefile.PE(str(path)) as pe:
            for entry in pe.DIRECTORY_ENTRY_RESOURCE.entries:
                group = group or entry.id == 14
                if entry.id == 3:
                    for resource in entry.directory.entries:
                        for language in resource.directory.entries:
                            item = language.data.struct
                            found.add(pe.get_data(item.OffsetToData, item.Size))
        if not group or not expected.issubset(found):
            raise base.ReleaseError("Embedded Windows icons do not match")
    else:
        contents = path / "Contents"
        with (contents / "Info.plist").open("rb") as stream:
            name = plistlib.load(stream).get("CFBundleIconFile", "")
        if not name or "/" in name or "\\" in name or name in (".", ".."):
            raise base.ReleaseError("Invalid bundle icon reference")
        if not name.endswith(".icns"):
            name += ".icns"
        if (contents / "Resources" / name).read_bytes() != icons.icns():
            raise base.ReleaseError("Embedded macOS icon does not match")


def run(args, cwd=None, extra_env=None, timeout=900, stage="command"):
    args, env = list(args), dict(extra_env or {})
    if stage == "source-tests":
        args = [sys.executable, base.ROOT / "ci/strict_tests.py"]
        env.update(REQUIRE_GUI="1", YTR_TEST_RESULTS=str(RESULTS))
    packaging = len(args) > 2 and args[1:3] == ["-m", "PyInstaller"]
    has_icon = packaging and (sys.platform == "win32" or "--windowed" in args)
    if has_icon:
        suffix = ".ico" if sys.platform == "win32" else ".icns"
        args.extend(["--icon", str(ICONS / ("app_icon" + suffix))])
    output = ORIGINAL_RUN(args, cwd, env, timeout=timeout, stage=stage)
    if has_icon:
        base.CURRENT_STAGE = "verify-embedded-icon"
        name = args[args.index("--name") + 1]
        extension = ".exe" if sys.platform == "win32" else ".app"
        verify_icon(base.PRIVATE / "frozen" / (name + extension))
    if stage == "dependency-manifest":
        destination = base.PRIVATE / "YandexTrackerReport"
        for name in ("app_icon.png", "app_icon.ico", "app_icon.icns"):
            base.shutil.copy2(ICONS / name, destination / name)
        base.shutil.copy2(RESULTS, destination / "TEST-RESULTS.json")
        base.shutil.copy2(base.SRC / "README.md", destination / "README.md")
    return output


def request(path, token_name, method="GET", data=None, optional=False):
    if path == "/releases" and method == "POST":
        if not isinstance(data, dict) or data.get("tag_name") != legacy.TAG or data.get("ref") != base.SOURCE:
            raise base.ReleaseError("Unexpected release target")
        data = dict(data)
        data["name"] = "Yandex Tracker Report 1.36.3 — сборка 56"
        data["description"] = (
            "## Версия 1.36.3, сборка 56\n\n"
            "Собственные иконки окна, обоих Windows EXE и macOS .app. "
            "Исходный коммит: `" + base.SOURCE + "`.\n\n"
            "## Проверки\n\n"
            "GitLab CI исходников прошёл успешно. На Windows x64, macOS Intel и Apple Silicon "
            "прошли все 42 исходных теста без ошибок, пропусков и ожидаемых ошибок. "
            "Проверены запуск и закрытие готового GUI, CLI --version/--help, "
            "встроенные ресурсы ICO и ICNS, helper Windows с -WhatIf, "
            "синтаксис helper macOS и целостность ad-hoc подписей. "
            "Размеры и SHA-256 архивов повторно проверены после загрузки.\n\n"
            "## Состав\n\n"
            "Три нативных архива, SHA256SUMS и BUILD-MANIFEST.json. "
            "В архивах: GUI, CLI, иконки, README.md, BUILDING.md, TRUST_AND_SECURITY.md, "
            "TEST-RESULTS.json, BINARY_SHA256SUMS и платформенный helper первого запуска.\n\n"
            "## Ограничения\n\n"
            "Windows без доверенной подписи издателя; macOS — ad-hoc без Developer ID/notarization. "
            "Предупреждения ОС возможны. Иконки и контрольные суммы не удостоверяют издателя. "
            "Helper не запускается автоматически, требует точного UNBLOCK и не меняет глобальную защиту. "
            "Реальные выгрузки Трекера и полный интерактивный сценарий не проверялись. "
            "Предыдущие релизы не изменены."
        )
    return ORIGINAL_REQUEST(path, token_name, method=method, data=data, optional=optional)


def check_tests(info):
    expected = {"run": 42, "failures": 0, "errors": 0, "skipped": 0, "expected_failures": 0, "unexpected_successes": 0}
    if info.get("strict_tests") != expected or info.get("embedded_icons") != "verified":
        raise base.ReleaseError("Strict test or icon verification is missing")


def build(target):
    base.CURRENT_STAGE = "generate-icons"
    load_icons().write_icons(ICONS)
    legacy.build(target)
    info_path = base.PRIVATE / (target + ".json")
    info = json.loads(info_path.read_text(encoding="utf-8"))
    info["strict_tests"] = json.loads(RESULTS.read_text(encoding="utf-8"))
    info["embedded_icons"] = "verified"
    check_tests(info)
    info_path.write_text(json.dumps(info), encoding="utf-8")


def publish():
    for target in base.TARGETS:
        info = base.read_json(base.PACKAGE + "/" + target + ".json")
        check_tests(info)
    legacy.publish()

base.run, base.request = run, request

if __name__ == "__main__":
    base.PRIVATE.mkdir(parents=True, exist_ok=True)
    try:
        mode = sys.argv[1] if len(sys.argv) == 2 else ""
        base.CURRENT_STAGE = mode
        target = os.environ.get("TARGET", "")
        if mode in ("build", "upload", "diagnostics") and target not in base.TARGETS:
            raise base.ReleaseError("Invalid build target")
        if mode == "preflight": base.preflight()
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
        print("Release failed at " + base.CURRENT_STAGE + ": " + detail + "; details in private GitLab diagnostics.", file=sys.stderr)
        sys.exit(1)
