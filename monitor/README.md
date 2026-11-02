# Automated native-build reporting

This workflow observes Native distributions to GitLab on main. It does not grant Actions tools to the external connector and does not build, retry, merge or publish application releases.

The job uses a short-lived GITHUB_TOKEN with contents:read and actions:read. Existing GITLAB_PUBLISH_TOKEN is used to store reports in GitLab project 21 and create/update one confidential issue per native workflow run. The read token is supplied only for redaction of known secrets. No additional personal access token is required.

Native workflow requested/in_progress/completed events trigger reports. Pushes affecting this monitor, its workflow or monitor-request.json also trigger a refresh of the three latest native runs, so installation retrieves recent failures without restarting native builds. Events and runner scheduling are not guaranteed to be instantaneous. No periodic polling or automatic repair loop is configured.

Each report includes run/job statuses, failed step names, a status.json snapshot and, after completion when available, the GitHub log ZIP in the GitLab generic package registry. Existing native build diagnostics for application version 1.36.1 are also read; up to 100 lines/12000 characters per target are copied into the confidential issue with known tokens redacted. The full native logs remain linked in GitLab. Package access follows GitLab project permissions. The raw GitHub log archive relies on GitHub's existing log masking; it is transferred only to GitLab, never unpacked or executed by this monitor.

The monitor checks out trusted main, does not execute source workflow commits, does not consume executable build artifacts and never prints private logs in public GitHub output. For issue updates, only a marked automation-owned description block is replaced; surrounding human text is preserved. Existing issues without that marker are not overwritten. Reports use new package versions on each monitor attempt; old snapshots are not deleted.

Reports can be read through the existing GitLab connector as issues/work items. This automates result collection, not unsolicited chat messages after an assistant response ends. API or token failures can still prevent reporting and will require investigation.
