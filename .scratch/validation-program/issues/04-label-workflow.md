# 04: Label workflow with calibration, blinding and adjudication

**What to build:** the human labeling loop as tooling. A calibration round of twenty cases produces the guide and measures labeling time per case. Full rounds generate packets that hide every detector output and the route's group where it could bias a label, take two independent label files, surface disagreements with both reasons, record an adjudication, and compute raw agreement, kappa and PABAK for at least the double-labeled sample. The output is L9-ready and names any case still needing a decision.

**Blocked by:** 01 (case record shape).

**Status:** ready-for-agent

- [ ] Packets contain no detector output and no field that reveals another labeler's answer
- [ ] Two fixture label files produce agreement, kappa and PABAK with known values
- [ ] Disagreements are listed with both labels and adjudication is recorded once
- [ ] A case without adjudication blocks the L9 output rather than defaulting
- [ ] Calibration records measured time per case
