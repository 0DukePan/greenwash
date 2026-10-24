# 01: Consent, export schema and the offline PR-log collector

**What to build:** the collector that turns a consented repository's merged PR export plus a local clone into the friction harness's PR-log format. It replays the static scan against each PR's merge base and head, records whether the PR touched tests, whether the scan flagged, the timestamps present and any override or opt-out markers, and marks every alert unreviewed. A repository absent from the consent record, a missing commit, a missing field, a malformed timestamp or a path leaving the clone is refused by name. It makes no network calls, runs no repository code, and bounds time per PR.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] A fixture export and local clone produce the harness's PR-log format with the required fields
- [ ] A repository without recorded consent is refused by name
- [ ] A missing commit, malformed timestamp or missing field is refused by name
- [ ] The collector runs offline, executes no repository code, and bounds time per PR
