# Yandex Tracker Report — build infrastructure

Public workflow repository only. Application source, native distributions, Releases and private diagnostics are maintained in GitLab project 21, m.smirnov/yandex-tracker-report. No application source or secrets are committed here.

Configured next target: version 1.36.2, build 55, tag v1.36.2, source e19b7355614e86e02d908aabefb33bc57bafc40f. This is a build configuration, not a claim that the release is already published. The previous confirmed release is v1.36.1.

Native distributions to GitLab starts on controlled main pushes affecting its workflow, ci/** or release-request.json. It waits for successful GitLab source CI, builds Windows x64/macOS Intel/macOS Apple Silicon, tests CLI/GUI, verifies uploaded SHA-256 and publishes only a complete release. Report native builds to GitLab mirrors statuses and available private diagnostic tails into confidential GitLab issues.

Keep the GitHub/GitLab connectors and this repository for future releases; account authorization and secret expiration may require renewal. Secrets remain in Actions Secrets. See BUILD.md and the main project's BUILDING.md for setup and release procedures. No trusted signing certificates are included; per-file helpers require explicit user confirmation and do not disable global protection.
