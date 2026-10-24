# 05: Baselines stage closes the competitor-overhead assumption

**What to build:** the baselines stage runs the pinned competitor and the other baselines over the assembled dev split, records their per-case results and measured cost and overhead, and closes the competitor-overhead assumption with the measured figures and artifact path. It refuses to close the assumption when a baseline result is missing or the competitor version is not pinned.

**Blocked by:** 04 (twins).

**Status:** ready-for-agent

- [ ] Baseline results are recorded per case with the pinned competitor version
- [ ] The competitor-overhead assumption closes with the measured figures and the artifact path
- [ ] A missing result or an unpinned competitor refuses and names the cause
- [ ] The baseline artifact carries the input hashes it consumed
