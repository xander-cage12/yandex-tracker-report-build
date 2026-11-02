# Native release 1.36.2, build 55

Entry point: ci/release_1_36_2.py, reusing ci/release.py as the base packager. It explicitly sets application version 1.36.2, build 55, source e19b7355614e86e02d908aabefb33bc57bafc40f and package version prefix 1.36.2. Release tag is v1.36.2, not v1.36.1-build55. Existing releases are never overwritten.

Only xander-cage12 on main can pass the native workflow guard. Standard Windows x64, macOS Intel and Apple Silicon public-repository runners are used. Existing GITLAB_READ_TOKEN (read_api) and GITLAB_PUBLISH_TOKEN (api) remain repository secrets; the monitor uses an ephemeral GITHUB_TOKEN with actions:read. No new PAT, source mirror, public artifact or dependency cache is created.

Preflight waits at most 30 minutes for successful GitLab CI on the pinned SHA; failed/canceled/skipped/manual CI stops release. Preflight/publish jobs time out at 35 minutes; native jobs at 45 minutes. Controlled push and workflow_dispatch triggers remain. GET/PUT retries, safe stage/HTTP errors and private logs are inherited from the base packager. Release POST is not retried.

All source tests and frozen CLI --version/--help plus GUI startup/exit smoke tests remain enabled. Native Windows archives exclude broad legacy sign_scripts/unblock_files helpers, include prepare_windows.ps1 and test it with -WhatIf. macOS archives include executable prepare_macos.command, check its syntax and existing app/CLI signature integrity. Both include BUILDING.md, TRUST_AND_SECURITY.md and generated BINARY_SHA256SUMS. Actual unblocking is not executed in CI.

The driver verifies helper presence in final archives, then verifies uploaded archive hashes and manifest source/version/build/run/tag before publication. Release assets contain three archives, SHA256SUMS and BUILD-MANIFEST.json. Partial packages may remain after failures; no partial release is advertised as complete.

monitor/report.py reads diagnostics under both 1.36.2 and historical 1.36.1 package prefixes, preserving access to prior failures. Its event-driven reporting continues after this chat ends, but does not send unsolicited chat messages or modify application code.

Helpers are opt-in per-file metadata operations, not trusted signatures. Windows remains unsigned; macOS ad-hoc signing is not Developer ID/notarization. OS warnings can remain. No global security policy, certificate trust store or antivirus exclusion is modified. Real Tracker exports and full desktop workflows were not tested. Update README status only after checking actual GitLab Release and complete assets; configuration alone is not publication.
