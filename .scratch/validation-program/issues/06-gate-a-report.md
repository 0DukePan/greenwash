# 06: Gate A report on the development split

**What to build:** a dev-only decision report that consumes the dev evaluation, the labelled cases and the baseline results, and returns go, pivot or stop with the numbers that decided it. It applies the fixed thresholds: go when H2 is confirmed and H3 holds with abstention at or below 0.20; pivot when Greenwash and the competitor are indistinguishable at the fixed n; stop when recall is clearly lower or abstention is above 0.20. It refuses to consume any frozen record, refuses when an unverified assumption sits in the assumptions register, and writes a machine-readable summary beside the report.

**Blocked by:** 04 (labels), 05 (twins for H2 and H3).

**Status:** ready-for-agent

- [ ] A fixture dev run yields go, pivot and stop under the three registered conditions
- [ ] The report names each hypothesis, its numbers, and the deciding threshold
- [ ] Any frozen record in the input refuses the run, naming it
- [ ] An open assumption in the register refuses the run, naming it
- [ ] The machine summary matches the report and contains no prose verdict
