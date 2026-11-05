"""Нативный выпуск 1.36.4: автоматический перенос настроек и 50 обязательных тестов."""
import json
import os
import sys
import traceback
import release_1_36_3 as previous

base = previous.base
base.SOURCE = "ea3e9f9136803e97423436d947ce95625c375316"
base.VERSION, base.BUILD = "1.36.4", "57"
base.PACKAGE = "/packages/generic/yandex-tracker-report/" + base.VERSION + "-" + base.RUN
previous.legacy.TAG = "v" + base.VERSION


def check_tests(info):
    expected = dict(run=50, failures=0, errors=0, skipped=0, expected_failures=0, unexpected_successes=0)
    if info.get("strict_tests") != expected or info.get("embedded_icons") != "verified":
        raise base.ReleaseError("Не подтверждены все 50 тестов без пропусков или встроенные иконки")


def run(args, cwd=None, extra_env=None, timeout=900, stage="command"):
    if stage == "source-tests":
        env = dict(extra_env or {})
        env.update(REQUIRE_GUI="1", YTR_TEST_RESULTS=str(previous.RESULTS))
        return previous.ORIGINAL_RUN([sys.executable, base.ROOT / "ci/strict_tests_1_36_4.py"],
                                     cwd, env, timeout=timeout, stage=stage)
    return previous.run(args, cwd, extra_env, timeout=timeout, stage=stage)


def request(path, token_name, method="GET", data=None, optional=False):
    if path == "/releases" and method == "POST":
        if not isinstance(data, dict) or data.get("tag_name") != "v1.36.4" or data.get("ref") != base.SOURCE:
            raise base.ReleaseError("Неожиданная цель публикации")
        data = dict(data)
        data["name"] = "Yandex Tracker Report 1.36.4 — сборка 57"
        data["description"] = (
            "## Версия 1.36.4, сборка 57\n\n"
            "Автоматический подхват OAuth-токена и предустановок при запуске GUI и CLI. "
            "Текущая конфигурация имеет приоритет. Если её нет, используется зарегистрированный путь, "
            "затем однозначно найденная соседняя установка. Учитывается config_location.txt. "
            "Перед копированием сохраняется резервная копия; старая установка не изменяется. "
            "При конфликте разных конфигураций перенос останавливается. "
            "Произвольное расположение старой незарегистрированной версии не обнаруживается. "
            "Автоматическая загрузка и замена исполняемых файлов в этот выпуск не входят.\n\n"
            "## Проверки\n\n"
            "GitLab CI закреплённого исходного коммита прошёл успешно. "
            "На Windows x64, macOS Intel и Apple Silicon прошли все 50 тестов без ошибок и пропусков. "
            "Проверены запуск GUI, CLI --version/--help, встроенные иконки, платформенные helper, "
            "целостность подписей macOS и SHA-256 загруженных архивов. "
            "Исходный коммит: `" + base.SOURCE + "`.\n\n"
            "## Ограничения\n\n"
            "Windows без доверенной подписи издателя; macOS — ad-hoc без Developer ID/notarization. "
            "Предупреждения ОС возможны. Полный интерактивный сценарий обновления и реальные выгрузки "
            "Трекера не проверялись. Предыдущие релизы не изменяются."
        )
    return previous.ORIGINAL_REQUEST(path, token_name, method=method, data=data, optional=optional)


previous.check_tests = check_tests
base.run, base.request = run, request

if __name__ == "__main__":
    base.PRIVATE.mkdir(parents=True, exist_ok=True)
    try:
        mode = sys.argv[1] if len(sys.argv) == 2 else ""
        base.CURRENT_STAGE = mode
        target = os.environ.get("TARGET", "")
        if mode in ("build", "upload", "diagnostics") and target not in base.TARGETS:
            raise base.ReleaseError("Неверная целевая платформа")
        if mode == "preflight": base.preflight()
        elif mode == "fetch": base.fetch()
        elif mode == "build": previous.build(target)
        elif mode == "upload": base.upload_build(target)
        elif mode == "diagnostics": base.diagnostics(target)
        elif mode == "release": previous.publish()
        else: raise base.ReleaseError("Неизвестная операция")
    except Exception as error:
        with base.LOG.open("a", encoding="utf-8") as stream:
            traceback.print_exc(file=stream)
        detail = str(error) if isinstance(error, base.ReleaseError) else type(error).__name__
        print("Ошибка выпуска на этапе " + base.CURRENT_STAGE + ": " + detail +
              "; подробности в приватной диагностике GitLab.", file=sys.stderr)
        sys.exit(1)
