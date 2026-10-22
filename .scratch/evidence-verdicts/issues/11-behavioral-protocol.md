# 11: Behavioral protocol runner with an independent instrument

**What to build:** the arms, the independent measurement, and the analysis input for the behavioral question. Arms are no skill, skill only, skill plus feedback, and optionally read-only tests, assigned per run and recorded on every row. The primary outcome comes from an instrument independent of the treatment: the hidden-test gap plus blinded review of every flagged case and a sample of unflagged ones. The checker's own flag rate is reported separately as a gate-hit rate. Blinded review packets are generated with the condition hidden, a key held outside them, and the analysis emits a risk difference with a confidence interval under a task-level clustering model. The sample size is fixed in advance and the runner refuses to peek.

**Blocked by:** 07 (corpus records), 09 (stats and gate machinery).

**Status:** ready-for-agent

- [ ] Every run row records its arm and the arm is never inferable from the scoring inputs
- [ ] The primary outcome is computed without reading the checker's verdict
- [ ] Packet generation hides condition and instruction references leaks the treatment
- [ ] The analysis prints the risk difference with a cluster-aware interval
- [ ] Impossible-task refusals are labeled from the construct, and the lower-bound convention is applied to tamper rates
