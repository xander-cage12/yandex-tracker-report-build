# Native release build

Application source is not stored in this public repository. Sources are fetched from pinned GitLab commit a556df07f7b7c7765970eed8245e278a2696f9f8 (version 1.36.1, build 54), including the Windows archive-path fix. GitLab pipeline 406 for this commit succeeded.

Required repository Actions secrets: GITLAB_READ_TOKEN (project read_api) and GITLAB_PUBLISH_TOKEN (project api). Never commit tokens. Only xander-cage12 can run this workflow from main.

Pushes to main affecting .github/workflows/native-release.yml, ci/** or release-request.json start a build automatically. Documentation-only pushes do not. Manual workflow_dispatch remains available. Changing release-request.json reruns the same pinned source/version, not another revision.

Only standard public-repository runners are used: windows-2025, macos-15-intel, macos-15. No GitHub artifacts or dependency caches are uploaded. Private source and detailed build logs remain on ephemeral runners. Diagnostics after build or upload failures are sent to GitLab when sources were fetched successfully. Public logs show controlled stage names and safe errors, not captured subprocess output. Package access follows GitLab project permissions.

GET/PUT requests have at most three attempts for network errors or HTTP 429/500/502/503/504, with bounded backoff. Other HTTP errors fail immediately. POST release creation is not retried. Retries do not prove the macOS Intel upload issue was transient; its actual error must be checked if it recurs.

The latest GitLab CI for the pinned main commit must succeed. All source tests and frozen CLI --version/--help and GUI startup/exit checks run on each target. All three builds must succeed and uploaded SHA-256 values must verify before publishing. Existing releases and mismatching tags are not overwritten. Partial packages may remain after a failed run. The separate monitor mirrors statuses and available diagnostic tails into confidential GitLab issues.

Windows includes portable EXEs and the application's BAT/PS1 helpers. macOS includes an app bundle and a CLI in tar.gz to preserve modes and symlinks. Python is bundled. No Windows publisher signature or Apple notarization is provided; macOS signing is ad-hoc. No security settings are disabled. Real Tracker exports and full interactive desktop workflows are not tested.

The packaging runtime hook puts default config/logs beside the executable or outside the macOS app bundle, with a per-user fallback if not writable. Application sources are not patched. Build metadata records source/workflow SHAs, Python/OS and dependencies. Dependencies other than PyInstaller are not locked; bit-for-bit reproducibility is not claimed.

Release target: GitLab project 21, v1.36.1, three native archives, SHA256SUMS and BUILD-MANIFEST.json. This commit requests a fresh build; successful native builds and publication are not yet verified.
