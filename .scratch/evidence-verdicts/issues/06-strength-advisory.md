# 06: Mutation-based strength advisory

**What to build:** on a normal run, mutants are introduced into the changed region and the suite is checked for whether it still discriminates. A suite that cannot catch the mutants sets the strength_low advisory flag without changing the verdict. The seed is fixed so the advisory is reproducible, and the cost is bounded by a per-run budget.

**Blocked by:** 01 (flag plumbing).

**Status:** ready-for-agent

- [ ] A known-weak suite fixture sets strength_low and its strong twin does not
- [ ] The verdict is identical with the advisory on and off
- [ ] Two runs on unchanged inputs produce the same advisory
- [ ] The advisory reports the mutant budget it spent
