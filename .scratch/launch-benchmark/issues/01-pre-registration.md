# 01: Pre-registration, thresholds and the burn ledger

**What to build:** a frozen manifest can be pre-registered once, and its evaluation history cannot be rewritten. Pre-registration stores the thresholds-file hash, the launch configuration id, detector hash and version, pinned baseline versions, taxonomy version, tool commit and manifest hash inside the manifest. The thresholds file is versioned data naming L1-L9 with their values. An append-only, hash-chained evaluation ledger records manifest, detector and thresholds hashes with the decision; an identical rerun must reproduce the same decision and bytes, and a rerun with a changed detector is refused. Every repository in an evaluated manifest is retired, and the corpus kit rejects any new frozen split that reuses one. Drifted frozen artifacts, drifted thresholds, drifted launch configuration or a missing baseline pin are refused before any evaluation.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] A manifest can be pre-registered once, and the record carries every hash the spec lists
- [ ] An identical rerun appends nothing and reproduces the decision and bytes
- [ ] A rerun with a changed detector hash is refused, and a changed threshold or launch configuration is refused
- [ ] Drifted frozen artifacts and missing baseline pins are refused, naming the artifact
- [ ] Evaluated repositories are retired, and a new split reusing one is rejected
- [ ] The refusal path writes no decision record and no report headline
