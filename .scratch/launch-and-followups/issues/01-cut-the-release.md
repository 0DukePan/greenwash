# 01: Cut and verify the 0.4.2 release

**What to build:** The release that has been sitting ready. The committed work lands on the public main branch, both tag spellings (`v0.4.2` and `greenwash--v0.4.2`) point at the release commit, a GitHub Release is published from the corrected notes, and a clean environment installs from the tag and reports the version. The release notes carry the corrected behavioural wording (a label count, not an effect claim) and the narrowed verifier-config rule.

**Blocked by:** None (can start immediately). Requires a push credential — the only prerequisite.

**Status:** ready-for-agent

- [ ] The remote main branch contains the release commit and its CI run is green
- [ ] Both tag spellings resolve to the same commit
- [ ] A GitHub Release exists, linking the release notes, the changelog section and the workflow run
- [ ] A clean environment installs from the tag and reports `greenwash 0.4.2`
- [ ] The release notes state the behavioural result as a label count on an instrument that could not measure the alternative, not as an effect
- [ ] The release notes describe the narrowed rule and link the before/after survey
