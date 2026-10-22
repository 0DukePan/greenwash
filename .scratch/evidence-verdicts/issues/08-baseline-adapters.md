# 08: Baseline adapters over the same corpus records

**What to build:** four detector baselines consume the same corpus records and emit comparable per-case outputs: a path rule that flags any test-file edit, a held-out-tests baseline where the source provides them, an LLM-judge harness with a frozen prompt and model run three times per case, and the close competitor run as a subprocess at a pinned version with its default configuration and no tuning.

**Blocked by:** 07 (corpus records).

**Status:** ready-for-agent

- [ ] Each baseline runs the fixture corpus and emits one comparable result per case
- [ ] The judge baseline reports its own run-to-run variance
- [ ] The competitor adapter records its pinned version in the output
- [ ] No evaluation-time knob exists that would let a baseline be tuned per case
