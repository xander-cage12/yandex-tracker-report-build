# Native release build

Application source is not stored in this public repository. Sources are fetched from the pinned GitLab commit 53bdfcc91683d2e51be3cba3d9c318bf301226ab (version 1.36.1, build 54).

Required repository Actions secrets: GITLAB_READ_TOKEN (project read_api) and GITLAB_PUBLISH_TOKEN (project api). Never commit tokens. Only xander-cage12 can run this workflow from main.

The workflow starts automatically on pushes to main that change .github/workflows/native-release.yml, ci/** or release-request.json. The commit enabling this trigger can start the first run. Changing release-request.json requests another run of the same pinned source/version; it does not select different sources. Documentation-only changes do not start builds. Manual workflow_dispatch remains available as a fallback.

Only standard free public-repository runners are used: windows-2025, macos-15-intel, macos-15. No GitHub artifacts or dependency caches are uploaded. Private source and detailed build logs remain on ephemeral runners; failed build logs are sent to the existing GitLab package registry. Package registry access follows GitLab project permissions.

The pinned main commit must have a successful GitLab pipeline. Source tests and frozen CLI --version/--help and GUI startup/exit smoke checks run on each target. Builds are uploaded to a run-specific GitLab package version; partial packages may remain if a build fails. No Release is created until all three builds succeed and uploaded checksums are verified. Existing releases and mismatching tags are not overwritten.

Windows includes portable EXEs and the application's BAT/PS1 helpers. macOS includes an app bundle and a CLI in a tar.gz archive to preserve modes and symlinks. Python is bundled. There is no Windows publisher signature or Apple notarization; macOS signing is ad-hoc. No security restrictions are disabled. Real Tracker exports and full interactive desktop use are not tested by this pipeline.

The packaging runtime hook changes default config/log paths to the executable directory, or beside the macOS app bundle; if that location is not writable it falls back to a per-user data folder. Application sources are not patched. Packaging entry-point behavior is the same as the source GUI, with an environment-controlled smoke-test exit. Build metadata records source and workflow SHAs, Python/OS versions and installed dependencies. Dependency versions other than PyInstaller are not locked; builds are not claimed to be bit-for-bit reproducible.

Release target in GitLab project 21: v1.36.1, three native archives, SHA256SUMS and BUILD-MANIFEST.json. Updating the pinned source/version requires a reviewed commit. Release creation takes place only after all required build and verification jobs succeed.
