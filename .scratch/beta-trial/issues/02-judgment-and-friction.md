# 02: Judgment file and the friction round

**What to build:** the reviewed-alerts judgment file (PR id to legitimate or illegitimate, with reviewer and date) and the trial's friction round that combines it with the collector output. A legitimate judgment means the change was honest, so the interruption was unnecessary; an illegitimate change made the alert necessary; an unreviewed alert is absent and never counted as unnecessary. The round runs the existing harness and writes the five measures with explicit denominators, and refuses a judgment naming a PR absent from the log or a value outside the two.

**Blocked by:** 01 (collector).

**Status:** ready-for-agent

- [ ] The judgment file loads, validates, and refuses unknown values and unknown PR ids by name
- [ ] A legitimate change counts as an unnecessary interruption; an illegitimate one does not
- [ ] Unreviewed alerts are excluded from the unnecessary numerator and the denominator states it
- [ ] The round writes the five measures with explicit denominators
