# 05: Verifier integrity and the integrity suite

**What to build:** the checker, its configuration and the pinned original tests are hash-verified before use and loaded from outside the agent's writable sandbox; in CI they come from the base ref, so a branch cannot lower its own bar. A scripted integrity suite attempts to alter checker inputs, configuration and output from inside a sandbox and requires zero successes. A modified checker or configuration fails loudly before any verdict is produced.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] A modified checker, config or pinned test is detected before the run starts
- [ ] The integrity suite reports zero successful modifications
- [ ] Base-ref loading is exercised by a test that edits the branch copy and still gets the base copy
- [ ] Integrity failure has its own exit code and never reads as a verdict about the diff
