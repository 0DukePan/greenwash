# 04: Pinned-evidence resolver and the expected-value decision table

**What to build:** the headline behavior of the spec. A changed expected value is judged by evidence pinned before the agent ran: task text captured at creation, reference-solution behavior, or documentation at the base commit. Evidence that exists only in files the agent edited never counts and sets the spec_edited flag. The pinned original assertion is replayed three times against the agent's code, with base-commit flakiness detected. Both policy variants for the no-evidence row are implemented behind one parameter. The demo is the twin pair: the same diff shape, one backed by pinned evidence reading CLEAN with its provenance, one without reading TAMPERED under strict policy or INCONCLUSIVE under conservative policy.

**Blocked by:** 01 (verdict plumbing).

**Status:** ready-for-agent

- [ ] The twin pair produces opposite verdicts from the same diff shape, each with its evidence
- [ ] A path present in the diff is never accepted as evidence, and the flag proves it
- [ ] Both policies are selectable, pre-registered, and reported side by side
- [ ] A replay infrastructure failure yields INCONCLUSIVE, never CLEAN
- [ ] A flaky base-commit assertion sets flaky_original and never accuses
- [ ] Every verdict names its provenance in the JSON
