# 09: Evaluation runner and mechanical gate evaluation

**What to build:** one command turns a corpus plus detector configurations into per-cell confusion matrices, strict recall and decided-case recall, false alarms on twins and natural clean passes, abstention, cost, wall time and run-to-run variance. Exact intervals are primary and Wilson is the sensitivity column. The pre-registered gates pass or fail mechanically against their thresholds, with the arithmetic printed, and per-cell tables are mandatory so no pooled number can be published alone. A frozen-manifest mismatch refuses to run.

**Blocked by:** 07 (corpus records), 08 (baselines).

**Status:** ready-for-agent

- [ ] The fixture corpus produces the exact expected table, interval arithmetic included
- [ ] Each gate reports pass or fail with the number that decided it
- [ ] A modified frozen case refuses to run and says which hash failed
- [ ] Synthetic and out-of-split records never enter a gate input
- [ ] Cost and variance appear next to every accuracy figure
