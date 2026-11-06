# 02: An unreadable changed file says so

**What to build:** A changed Python source file that the parser cannot read stops reading as clean. Today such a change reports "no suspicious patterns" and the run moves on, which is the same defect the project already refuses elsewhere: a check that could not run must not read as a pass. The report names the affected file, says the static layer could not check it, and a report carrying that gap cannot be `CLEAN` or `VERIFIED`. The same finding appears in the JSON report.

**Blocked by:** None (can start immediately).

**Status:** done — merged `7d8bddd`, review fixes `9579da2` on `integration/launch-followups`. The finding is `unreadable-file` (GW-DIV-003), covering both a file that will not parse and one git reports as binary; a missing path is still not a finding.

- [ ] A changed file that fails to parse produces a finding naming that file, in text and JSON
- [ ] A report with such a gap cannot be `CLEAN` or `VERIFIED`
- [ ] The finding is distinguishable from both "no signals" and a tampering allegation — it says the check could not run, not that the change is wrong
- [ ] A well-formed changed file produces no such finding
- [ ] The existing byte-order-mark handling and its regression tests are unaffected
- [ ] The rule table in the README and the generated rules listing stay in agreement if a rule id is introduced
