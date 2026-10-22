# 01: Evidence verdicts in the report

**What to build:** every verification run answers in one of four evidence verdicts, TAMPERED, INCONCLUSIVE, WEAK_VERIFIER or CLEAN, with a fixed precedence when findings overlap. The JSON report carries the verdict, optional secondary flags (spec_edited, strength_low, edits_listed, flaky_original, replay_infra_error), and for every finding the mechanism and the grade relevance as separate fields. Today's runs classify exactly as they do now, so this lands green as a prefactor for everything after it.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] Recorded runs classify identically before and after the change
- [ ] TAMPERED cannot be emitted without both mechanism and grade relevance
- [ ] Precedence resolves overlapping findings, and no finding is dropped
- [ ] The exit-code table is documented and tested for every verdict
- [ ] The report JSON is stable enough for a user to store beside a CI run
